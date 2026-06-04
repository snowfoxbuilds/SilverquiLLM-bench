"""Tests for SOS 245 — Witherbloom, the Balancer.

Witherbloom, the Balancer is a {6}{B}{G} Legendary Creature — Elder Dragon,
5/5, with:

1. **Affinity for creatures** — "This spell costs {1} less to cast for each
   creature you control." Modeled via the ``cost_reduction(game)`` hook (only
   the generic portion of the cost is reduced; the {B}{G} pips never are).
2. **Flying** and **Deathtouch** keywords.
3. **Granted affinity** — "Instant and sorcery spells you cast have affinity
   for creatures." The engine has no central cost-reduction registry, so (as
   with FDN 159's analogous "cost {1} less" clause) the granting is modeled via
   a marker the casting system can consult. These tests assert what is
   observable; the granting plumbing is recorded in untestable.json.

These tests define the TDD contract; ``card_impl.py`` is a stub, so they are
expected to fail until the card is implemented.
"""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature
from engine.combat import _can_block, _get_lethal_damage
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bear(name: str = "Grizzly Bears") -> Creature:
    """A vanilla 2/2 creature with no keywords."""
    c = Creature(name=name, base_power=2, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    c.keywords = Keyword(0)
    return c


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestWitherbloomProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)
        assert CardType.CREATURE in WitherbloomTheBalancer(owner=None).card_types

    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in WitherbloomTheBalancer(owner=None).supertypes

    def test_is_elder_dragon(self) -> None:
        subtypes = WitherbloomTheBalancer(owner=None).subtypes
        assert "Dragon" in subtypes
        assert "Elder" in subtypes


# ---------------------------------------------------------------------------
# Keywords (printed)
# ---------------------------------------------------------------------------


class TestWitherbloomKeywords:
    """Flying and Deathtouch are printed on the card."""

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in WitherbloomTheBalancer(owner=None).keywords

    def test_has_deathtouch(self) -> None:
        assert Keyword.DEATHTOUCH in WitherbloomTheBalancer(owner=None).keywords

    def test_does_not_have_unrelated_keyword(self) -> None:
        # Sanity: it should not pick up keywords it doesn't have.
        assert Keyword.TRAMPLE not in WitherbloomTheBalancer(owner=None).keywords


# ---------------------------------------------------------------------------
# Affinity for creatures (cost reduction on its own cast)
# ---------------------------------------------------------------------------


class TestWitherbloomAffinity:
    """cost_reduction reduces generic mana by 1 per creature you control."""

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_reduction_equals_creature_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B"), _bear("C")])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 3

    def test_self_counts_when_on_battlefield_does_not_inflate(self) -> None:
        """Reduction counts creatures the controller controls; with exactly
        two other creatures the reduction is 2."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B")])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 2

    def test_only_counts_creatures(self) -> None:
        """Non-creature permanents do not contribute to affinity for creatures."""
        from engine.card import Artifact, Enchantment

        game = create_game()
        p1 = game.players[0]
        artifact = Artifact(name="Mind Stone")
        enchantment = Enchantment(name="Random Aura")
        set_board_state(game, 0, battlefield=[_bear("A"), artifact, enchantment])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_only_counts_your_creatures(self) -> None:
        """Opponent's creatures do not reduce the cost."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[_bear("Mine A"), _bear("Mine B")])
        set_board_state(game, 1, battlefield=[_bear("Theirs A"), _bear("Theirs B"),
                                              _bear("Theirs C")])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 2

    def test_reduction_clamped_to_generic_via_pipeline(self) -> None:
        """Even with many creatures, only the {6} generic is reducible — the
        {B}{G} pips remain. get_cost_reduction clamps the raw value to 6."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[_bear(f"Bear{i}") for i in range(9)])
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Raw cost_reduction is 9, but clamped to the {6} generic.
        assert get_cost_reduction(game, card, p1) == 6


# ---------------------------------------------------------------------------
# Casting with affinity (integration through the cast pipeline)
# ---------------------------------------------------------------------------


class TestWitherbloomCastingWithAffinity:
    """The reduced cost is what the cast pipeline charges."""

    def test_cast_with_three_creatures_pays_reduced_generic(self) -> None:
        """With 3 creatures, {6}{B}{G} → {3}{B}{G}. Player with 3 generic +
        B + G casts successfully and the spell hits the stack."""
        from engine.casting import cast_spell

        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        # Witherbloom is a (non-flash) creature, so it can only be cast at
        # sorcery speed. create_game() starts in Phase.BEGINNING, where the
        # cast would be rejected; move to a main phase first.
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B"), _bear("C")])

        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_hand(p1).add(card)
        set_board_state(
            game,
            0,
            mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        cast_spell(game, p1, card)
        assert not game.stack.is_empty()

    def test_cast_without_enough_mana_for_reduced_cost_fails(self) -> None:
        """With only 1 creature the reduction is just 1; {5}{B}{G} cannot be
        paid with {3}{B}{G} worth of mana."""
        import pytest
        from engine.casting import cast_spell, CastingError

        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        set_board_state(game, 0, battlefield=[_bear("A")])

        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_hand(p1).add(card)
        set_board_state(
            game,
            0,
            mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )

        with pytest.raises(CastingError):
            cast_spell(game, p1, card)

    def test_colored_pips_never_reduced(self) -> None:
        """Affinity cannot pay the {B}{G}: with 8 creatures and only colorless
        mana, the cast fails because the colored pips remain unpaid."""
        import pytest
        from engine.casting import cast_spell, CastingError

        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        set_board_state(game, 0, battlefield=[_bear(f"B{i}") for i in range(8)])

        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_hand(p1).add(card)
        # Plenty of colorless, but no black/green for the pips.
        set_board_state(game, 0, mana={ManaType.COLORLESS: 10})

        with pytest.raises(CastingError):
            cast_spell(game, p1, card)


# ---------------------------------------------------------------------------
# Flying — combat blocking restriction
# ---------------------------------------------------------------------------


class TestWitherbloomFlying:
    """Flying restricts which creatures can legally block this attacker."""

    def test_ground_creature_cannot_block(self) -> None:
        attacker = WitherbloomTheBalancer(owner=None)
        blocker = _bear("Ground")
        assert _can_block(blocker, attacker) is False

    def test_flying_blocker_can_block(self) -> None:
        attacker = WitherbloomTheBalancer(owner=None)
        blocker = _bear("Air")
        blocker.keywords = Keyword.FLYING
        assert _can_block(blocker, attacker) is True

    def test_reach_blocker_can_block(self) -> None:
        attacker = WitherbloomTheBalancer(owner=None)
        blocker = _bear("Spider")
        blocker.keywords = Keyword.REACH
        assert _can_block(blocker, attacker) is True


# ---------------------------------------------------------------------------
# Deathtouch — lethal damage
# ---------------------------------------------------------------------------


class TestWitherbloomDeathtouch:
    """Deathtouch makes any nonzero damage from Witherbloom lethal."""

    def test_one_damage_is_lethal_against_high_toughness(self) -> None:
        attacker = WitherbloomTheBalancer(owner=None)
        big = _bear("Big Wall")
        big.modified_toughness = 10
        # With deathtouch, only 1 damage is needed to be lethal.
        assert _get_lethal_damage(big, attacker) == 1

    def test_without_deathtouch_lethal_is_toughness(self) -> None:
        """Control: a non-deathtouch attacker needs full toughness in damage."""
        plain = _bear("Plain")
        big = _bear("Big Wall")
        big.modified_toughness = 10
        assert _get_lethal_damage(big, plain) == 10


# ---------------------------------------------------------------------------
# Granted affinity to instants/sorceries (best-effort observable contract)
# ---------------------------------------------------------------------------


class TestWitherbloomGrantsAffinity:
    """"Instant and sorcery spells you cast have affinity for creatures."

    The engine has no central cost-reduction registry (see FDN 159), so the
    grant is exercised here only at the level the engine can observe:
    register_triggers/register_replacement_effects must not raise, and any
    marker the card sets must reference its controller. The actual cost
    reduction of *other* spells is recorded in untestable.json.
    """

    def test_register_triggers_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Must not raise when wiring up the granted-affinity machinery.
        card.register_triggers(game)

    def test_card_advertises_no_spell_targets(self) -> None:
        """Witherbloom is a vanilla-cast permanent (its abilities are static),
        so get_targets must be empty — casting it must not demand a target."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.get_targets(game) == []


# ---------------------------------------------------------------------------
# Granted affinity — cost-reduction registry (engine now BUILT)
# ---------------------------------------------------------------------------
#
# "Instant and sorcery spells you cast have affinity for creatures." The
# engine now exposes a game-level cost-reduction registry
# (GameState.spell_cost_reducers + register/unregister/
# spell_cost_reduction_from_reducers), summed by
# engine.casting.get_cost_reduction alongside each spell's own
# cost_reduction() hook. Witherbloom registers a reducer (in register_triggers)
# that grants affinity-for-creatures to its controller's OTHER instant/sorcery
# spells while it is on the battlefield. These tests exercise that grant on a
# SEPARATE spell — the behavior previously recorded in untestable.json.


def _test_instant(name: str = "Test Bolt", generic: int = 4, color: str = "R"):
    """A vanilla instant with a generic-heavy cost (default ``{4}{R}``).

    Used as the *other* instant/sorcery spell whose cost Witherbloom's granted
    affinity should reduce. Kept deliberately simple — no abilities, no
    cost_reduction() hook of its own — so any reduction observed comes purely
    from the registry.
    """
    from engine.card import Instant
    from engine.types import ManaCost

    return Instant(name=name, mana_cost=ManaCost.parse(f"{{{generic}}}{{{color}}}"))


def _test_sorcery(name: str = "Test Bolt Sorcery", generic: int = 4, color: str = "R"):
    """A vanilla sorcery counterpart to :func:`_test_instant`."""
    from engine.card import Sorcery
    from engine.types import ManaCost

    return Sorcery(name=name, mana_cost=ManaCost.parse(f"{{{generic}}}{{{color}}}"))


def _witherbloom_on_battlefield(game, player, *, creatures):
    """Put Witherbloom + *creatures* on *player*'s battlefield and wire up the
    granted-affinity reducer.

    ``set_board_state`` drops cards straight into the zone without firing the
    normal ETB plumbing, so the reducer Witherbloom registers in
    ``register_triggers`` must be activated explicitly here — mirroring what
    ``move_to_zone`` does when a permanent actually enters the battlefield.
    """
    wb = WitherbloomTheBalancer(owner=player, controller=player)
    set_board_state(
        game,
        game.players.index(player),
        battlefield=[wb] + list(creatures),
    )
    wb.register_triggers(game)
    return wb


class TestWitherbloomGrantsAffinityRegistry:
    """Granted affinity reduces the controller's OTHER instant/sorcery spells
    via the engine's spell cost-reduction registry."""

    def test_separate_instant_reduced_by_creature_count(self) -> None:
        """With Witherbloom + 3 bears on the battlefield, a separate {6}{R}
        instant the controller casts has its generic reduced by 4 — the bears
        AND Witherbloom itself all count as creatures you control."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear("A"), _bear("B"), _bear("C")]
        _witherbloom_on_battlefield(game, p1, creatures=bears)

        bolt = _test_instant(generic=6)
        bolt.controller = p1
        bolt.owner = p1
        # 3 bears + Witherbloom = 4 creatures -> generic reduced by 4
        # (within the {6} generic, no clamp).
        assert get_cost_reduction(game, bolt, p1) == 4

    def test_separate_sorcery_reduced_by_creature_count(self) -> None:
        """The grant applies to sorceries too, not just instants."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear("A"), _bear("B")]
        _witherbloom_on_battlefield(game, p1, creatures=bears)

        sorc = _test_sorcery(generic=6)
        sorc.controller = p1
        sorc.owner = p1
        # 2 bears + Witherbloom = 3 creatures -> reduction 3.
        assert get_cost_reduction(game, sorc, p1) == 3

    def test_reduction_tracks_creature_count_changes(self) -> None:
        """The granted affinity scales with the controller's creature count:
        adding a creature increases the reduction."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        wb = _witherbloom_on_battlefield(game, p1, creatures=[_bear("A")])

        bolt = _test_instant(generic=6)
        bolt.controller = p1
        bolt.owner = p1
        # 1 bear + Witherbloom = 2 creatures -> reduction 2.
        assert get_cost_reduction(game, bolt, p1) == 2

        # Add two more bears alongside Witherbloom; 3 bears + Witherbloom = 4.
        set_board_state(game, 0, battlefield=[wb, _bear("A"), _bear("B"), _bear("C")])
        assert get_cost_reduction(game, bolt, p1) == 4

    def test_clamped_when_creature_count_exceeds_generic(self) -> None:
        """Affinity reduces only the generic — with 6 creatures a {2}{R} spell
        drops to {0}{R} (clamped at 0), never below."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear(f"Bear{i}") for i in range(6)]
        _witherbloom_on_battlefield(game, p1, creatures=bears)

        bolt = _test_instant(generic=2)
        bolt.controller = p1
        bolt.owner = p1
        # 6 creatures, but only {2} generic is reducible -> clamped to 2.
        assert get_cost_reduction(game, bolt, p1) == 2

    def test_witherbloom_does_not_reduce_its_own_spell_via_registry(self) -> None:
        """The registered reducer excludes Witherbloom itself — a second
        Witherbloom being cast is reduced only by its own affinity hook, not
        doubled by the registry."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear("A"), _bear("B")]
        _witherbloom_on_battlefield(game, p1, creatures=bears)

        # A different Witherbloom copy being cast: its own cost_reduction()
        # counts the 2 bears (the battlefield Witherbloom is a creature too,
        # so 3 creatures total), but the registry's predicate skips
        # instant/sorcery only — a creature spell gets no registry bonus.
        second = WitherbloomTheBalancer(owner=p1, controller=p1)
        reduction = get_cost_reduction(game, second, p1)
        # 3 creatures you control (2 bears + the battlefield Witherbloom) ->
        # reduction 3 from its OWN hook; the registry adds nothing for a
        # creature spell. Clamped within the {6} generic.
        assert reduction == 3

    def test_opponent_instant_not_reduced(self) -> None:
        """The grant is "spells YOU cast" — an opponent's instant gets no
        reduction even with Witherbloom + creatures on the controller's side."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear("A"), _bear("B"), _bear("C")]
        _witherbloom_on_battlefield(game, p1, creatures=bears)

        opp_bolt = _test_instant(name="Opp Bolt", generic=4)
        opp_bolt.controller = p2
        opp_bolt.owner = p2
        # p2 is not Witherbloom's controller -> no granted affinity.
        assert get_cost_reduction(game, opp_bolt, p2) == 0

    def test_creature_spell_not_reduced_by_grant(self) -> None:
        """The grant applies to instant/sorcery spells only — a separate
        creature spell the controller casts gets no registry reduction."""
        from engine.casting import get_cost_reduction
        from engine.types import ManaCost

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear("A"), _bear("B"), _bear("C")]
        _witherbloom_on_battlefield(game, p1, creatures=bears)

        plain_creature = Creature(
            name="Hill Giant", base_power=3, base_toughness=3,
            mana_cost=ManaCost.parse("{4}{R}"),
        )
        plain_creature.card_types = {CardType.CREATURE}
        plain_creature.controller = p1
        plain_creature.owner = p1
        # A vanilla creature has no cost_reduction() hook of its own and the
        # registry skips non-instant/sorcery spells -> no reduction.
        assert get_cost_reduction(game, plain_creature, p1) == 0

    def test_no_reduction_without_witherbloom_on_battlefield(self) -> None:
        """Registry no-op: without Witherbloom in play, the same {4}{R} instant
        gets no affinity reduction even with creatures on the battlefield."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        # Creatures but NO Witherbloom -> no reducer registered.
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B"), _bear("C")])

        bolt = _test_instant(generic=4)
        bolt.controller = p1
        bolt.owner = p1
        assert get_cost_reduction(game, bolt, p1) == 0

    def test_unregister_removes_grant(self) -> None:
        """After Witherbloom's reducer is unregistered (e.g. it leaves the
        battlefield), the controller's instant gets no further reduction."""
        from engine.casting import get_cost_reduction

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear("A"), _bear("B"), _bear("C")]
        wb = _witherbloom_on_battlefield(game, p1, creatures=bears)

        bolt = _test_instant(generic=6)
        bolt.controller = p1
        bolt.owner = p1
        # 3 bears + Witherbloom = 4 creatures -> reduction 4.
        assert get_cost_reduction(game, bolt, p1) == 4

        game.unregister_spell_cost_reducer(wb)
        assert get_cost_reduction(game, bolt, p1) == 0

    def test_cast_separate_instant_pays_reduced_cost(self) -> None:
        """End-to-end: with Witherbloom + 3 bears (4 creatures), the controller
        casts a separate {6}{R} instant for {2}{R} and it reaches the stack."""
        from engine.casting import cast_spell

        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bears = [_bear("A"), _bear("B"), _bear("C")]
        _witherbloom_on_battlefield(game, p1, creatures=bears)

        bolt = _test_instant(generic=6)
        game.get_hand(p1).add(bolt)
        bolt.controller = p1
        bolt.owner = p1
        # {6}{R} reduced by 4 -> {2}{R}: exactly 2 colorless + 1 red pays it.
        set_board_state(
            game,
            0,
            mana={ManaType.COLORLESS: 2, ManaType.RED: 1},
        )

        cast_spell(game, p1, bolt)
        assert not game.stack.is_empty()
