"""Tests for SOS 245 — Witherbloom, the Balancer.

Witherbloom, the Balancer is a ``{6}{B}{G}`` Legendary Creature — Elder
Dragon with power/toughness 5/5 and the following abilities:

1. "Affinity for creatures (This spell costs {1} less to cast for each
   creature you control.)" — a cost-reduction mechanic on the dragon itself.
2. "Flying, deathtouch" (evergreen keywords).
3. "Instant and sorcery spells you cast have affinity for creatures." — the
   dragon grants affinity-for-creatures cost reduction to every instant/sorcery
   its controller casts.

Affinity is modeled in this codebase through the ``cost_reduction(game)`` hook
(see FDN 6 Claws Out, which implements "Affinity for Cats" by counting Cats the
controller controls). The engine clamps the returned value to the generic
portion of the mana cost (``engine.casting.get_cost_reduction``), so colored
mana is never reduced and generic never drops below zero.

The third ability grants affinity to *other* spells. The engine's
``get_cost_reduction`` only consults a card's own ``cost_reduction`` hook, so —
mirroring the SOS 226 casualty-granting and SOS 201 miracle-granting
conventions — the granted ability is exposed through a capability the engine's
cost-reduction path can query:

* ``grants_affinity_to(spell) -> bool`` — True for instant/sorcery spells the
  dragon's controller casts, False otherwise.
* ``affinity_reduction(game) -> int`` — the affinity-for-creatures reduction
  value (the number of creatures the controller controls), the same value the
  dragon applies to itself and grants to instants/sorceries.

These tests target the public card contract and are written before the
implementation (TDD red phase): they import ``WitherbloomTheBalancer`` and
assert real behavior, so they fail until the card is implemented.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery, Land
from engine.casting import (
    cast_spell as engine_cast_spell,
    get_cost_reduction,
)
from engine.combat import _can_block, _get_lethal_damage
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creature(name: str, power: int = 1, toughness: int = 1, owner=None) -> Creature:
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        owner=owner,
        controller=owner,
    )


def _make_instant(name: str = "Test Bolt", cost: str = "{3}{R}", owner=None) -> Instant:
    return Instant(
        name=name,
        mana_cost=ManaCost.parse(cost),
        owner=owner,
        controller=owner,
    )


def _make_sorcery(name: str = "Test Divination", cost: str = "{4}{U}", owner=None) -> Sorcery:
    return Sorcery(
        name=name,
        mana_cost=ManaCost.parse(cost),
        owner=owner,
        controller=owner,
    )


# ---------------------------------------------------------------------------
# Static characteristics
# ---------------------------------------------------------------------------


class TestWitherbloomProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_mana_value_is_eight(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost.cmc == 8

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in WitherbloomTheBalancer(owner=None).supertypes

    def test_elder_dragon_subtypes(self) -> None:
        subtypes = WitherbloomTheBalancer(owner=None).subtypes
        assert {"Elder", "Dragon"} <= subtypes

    def test_colors_are_black_green(self) -> None:
        """The spec lists colors B and G; cards advertise this via self.colors."""
        colors = set(getattr(WitherbloomTheBalancer(owner=None), "colors", []))
        assert colors == {"B", "G"}


# ---------------------------------------------------------------------------
# Flying + deathtouch keywords
# ---------------------------------------------------------------------------


class TestWitherbloomKeywords:
    """Flying and deathtouch keyword flags and their combat-rule consequences."""

    def test_has_flying_and_deathtouch(self) -> None:
        kw = WitherbloomTheBalancer(owner=None).keywords
        assert Keyword.FLYING in kw
        assert Keyword.DEATHTOUCH in kw

    def test_does_not_have_unrelated_keywords(self) -> None:
        """The spec lists exactly flying + deathtouch (Affinity is not an
        engine Keyword flag). Guard against accidental extra keywords."""
        kw = WitherbloomTheBalancer(owner=None).keywords
        assert Keyword.TRAMPLE not in kw
        assert Keyword.VIGILANCE not in kw
        assert Keyword.LIFELINK not in kw

    def test_ground_creature_cannot_block_flying_witherbloom(self) -> None:
        attacker = WitherbloomTheBalancer(owner=None)
        ground = Creature(name="Ground Bear", base_power=2, base_toughness=2)
        ground.keywords = Keyword(0)
        ground.is_tapped = False
        assert _can_block(ground, attacker) is False

    def test_flying_creature_can_block_flying_witherbloom(self) -> None:
        attacker = WitherbloomTheBalancer(owner=None)
        # Guard: contract is meaningful only if Witherbloom actually flies.
        assert Keyword.FLYING in attacker.keywords
        flier = Creature(name="Air Bear", base_power=2, base_toughness=2)
        flier.keywords = Keyword.FLYING
        flier.is_tapped = False
        assert _can_block(flier, attacker) is True

    def test_reach_creature_can_block_flying_witherbloom(self) -> None:
        attacker = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in attacker.keywords
        spider = Creature(name="Spider", base_power=1, base_toughness=4)
        spider.keywords = Keyword.REACH
        spider.is_tapped = False
        assert _can_block(spider, attacker) is True

    def test_deathtouch_makes_one_damage_lethal(self) -> None:
        """Deathtouch (CR 702.2): any nonzero damage from Witherbloom is lethal.

        ``_get_lethal_damage`` returns 1 when the damage source has deathtouch,
        regardless of the victim's toughness.
        """
        dragon = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in dragon.keywords
        big = Creature(name="Colossus", base_power=10, base_toughness=10)
        assert _get_lethal_damage(big, dragon) == 1

    def test_no_deathtouch_source_needs_full_toughness(self) -> None:
        """Control: a non-deathtouch source needs toughness-worth of damage.

        This isolates that the lethal=1 result above is caused by Witherbloom's
        deathtouch and not by some unrelated quirk of ``_get_lethal_damage``.
        """
        plain = Creature(name="Plain Bear", base_power=2, base_toughness=2)
        big = Creature(name="Colossus", base_power=10, base_toughness=10)
        assert _get_lethal_damage(big, plain) == 10


# ---------------------------------------------------------------------------
# Affinity for creatures: the dragon's OWN cost reduction
# ---------------------------------------------------------------------------


class TestWitherbloomOwnAffinity:
    """"Affinity for creatures" — Witherbloom costs {1} less per creature you
    control. Modeled via the ``cost_reduction(game)`` hook (FDN 6 convention).
    """

    def test_cost_reduction_counts_zero_with_no_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        assert dragon.cost_reduction(game) == 0

    def test_cost_reduction_counts_creatures_you_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = _make_creature("Bear A", owner=p1)
        c2 = _make_creature("Bear B", owner=p1)
        c3 = _make_creature("Bear C", owner=p1)
        set_board_state(game, 0, battlefield=[c1, c2, c3])
        assert dragon.cost_reduction(game) == 3

    def test_cost_reduction_ignores_opponents_creatures(self) -> None:
        """Affinity counts creatures *you* control, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        mine = _make_creature("Mine", owner=p1)
        set_board_state(game, 0, battlefield=[mine])
        opp1 = _make_creature("Theirs A", owner=p2)
        opp2 = _make_creature("Theirs B", owner=p2)
        set_board_state(game, 1, battlefield=[opp1, opp2])
        assert dragon.cost_reduction(game) == 1

    def test_cost_reduction_ignores_noncreature_permanents(self) -> None:
        """Lands and other non-creatures do not count toward affinity."""
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        creature = _make_creature("Bear", owner=p1)
        forest = Land(name="Forest")
        forest.owner = p1
        forest.controller = p1
        set_board_state(game, 0, battlefield=[creature, forest])
        assert dragon.cost_reduction(game) == 1

    def test_get_cost_reduction_clamped_to_generic(self) -> None:
        """The engine clamps affinity to the generic portion: {6}{B}{G} can be
        reduced by at most 6 even if the controller has more creatures."""
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_creature(f"Bear {i}", owner=p1) for i in range(9)]
        set_board_state(game, 0, battlefield=list(creatures))
        # Raw count is 9, but only the {6} generic is reducible.
        assert get_cost_reduction(game, dragon, p1) == 6

    def test_real_cast_pays_reduced_cost(self) -> None:
        """End-to-end: with 3 creatures in play, casting Witherbloom costs
        {3}{B}{G} instead of {6}{B}{G}. Drive the REAL cast pipeline and check
        the mana actually consumed.
        """
        game = create_game()
        p1 = game.players[0]
        c1 = _make_creature("Bear A", owner=p1)
        c2 = _make_creature("Bear B", owner=p1)
        c3 = _make_creature("Bear C", owner=p1)
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[c1, c2, c3])
        # Hand: the dragon; pool: 3 generic (colorless) + B + G — exactly the
        # reduced cost {3}{B}{G}.
        set_board_state(
            game,
            0,
            hand=[dragon],
            mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        engine_cast_spell(game, p1, dragon)

        # Successfully cast: the dragon is on the stack and the pool is emptied
        # by the reduced cost (3 generic auto-paid by colorless, B and G pips).
        assert any(
            getattr(so, "source", None) is dragon for so in game.stack.objects()
        )
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        assert p1.mana_pool.get(ManaType.BLACK) == 0
        assert p1.mana_pool.get(ManaType.GREEN) == 0
        # mana_spent reflects the reduced converted cost: 3 generic + B + G = 5.
        assert getattr(dragon, "mana_spent", None) == 5


# ---------------------------------------------------------------------------
# Granted affinity: "Instant and sorcery spells you cast have affinity for
# creatures" — capability contract
# ---------------------------------------------------------------------------


class TestWitherbloomGrantedAffinityCapability:
    """The dragon advertises a capability for granting affinity to the
    controller's instant/sorcery spells, queried by the cost-reduction path.

    Following the SOS 226 ``grants_casualty_to`` / SOS 201 ``grants_miracle_to``
    convention, the dragon exposes:

    * ``grants_affinity_to(spell) -> bool`` (truthy for instant/sorcery only)
    * ``affinity_reduction(game) -> int`` (the creature count; the granted
      reduction value).
    """

    def test_grants_affinity_to_instant(self) -> None:
        dragon = WitherbloomTheBalancer(owner=None)
        assert bool(dragon.grants_affinity_to(_make_instant())) is True

    def test_grants_affinity_to_sorcery(self) -> None:
        dragon = WitherbloomTheBalancer(owner=None)
        assert bool(dragon.grants_affinity_to(_make_sorcery())) is True

    def test_does_not_grant_affinity_to_creature_spell(self) -> None:
        dragon = WitherbloomTheBalancer(owner=None)
        bear = _make_creature("Bear", 2, 2)
        assert not dragon.grants_affinity_to(bear)

    def test_does_not_grant_affinity_to_land(self) -> None:
        dragon = WitherbloomTheBalancer(owner=None)
        assert not dragon.grants_affinity_to(Land(name="Forest"))

    def test_affinity_reduction_counts_controllers_creatures(self) -> None:
        """The granted reduction value equals the number of creatures the
        dragon's controller controls — the same affinity metric the dragon
        uses for itself."""
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = _make_creature("Bear A", owner=p1)
        c2 = _make_creature("Bear B", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, c1, c2])
        # Itself + 2 bears = 3 creatures the controller controls.
        assert dragon.affinity_reduction(game) == 3


# ---------------------------------------------------------------------------
# Granted affinity: end-to-end through the real cast pipeline
# ---------------------------------------------------------------------------


class TestWitherbloomGrantedAffinityIntegration:
    """When Witherbloom is in play, an instant/sorcery the controller casts is
    reduced by {1} per creature the controller controls — driven through the
    REAL ``engine.casting.cast_spell`` pipeline.

    This is the true requirement of the third ability. The default engine
    ``get_cost_reduction`` only consults the spell's own ``cost_reduction``
    hook, so realizing this needs the dragon to be consulted at cast time
    (either via an additive engine hook the implementer adds, or by the card
    wiring the reduction). These tests assert the observable result regardless
    of the chosen wiring; they intentionally fail until that wiring exists.
    """

    def _setup_main_phase(self, game, player_index: int) -> None:
        game.active_player_index = player_index
        game.priority_player_index = player_index
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    def test_controllers_instant_gets_affinity_reduction(self) -> None:
        """A {3}{R} instant cast with Witherbloom + 2 other creatures in play
        (3 creatures total) should cost only {R}: the {3} generic is wholly
        reduced. Provide exactly {R} and confirm the cast succeeds."""
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = _make_creature("Bear A", owner=p1)
        c2 = _make_creature("Bear B", owner=p1)
        bolt = _make_instant("Affinity Bolt", cost="{3}{R}", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, c1, c2])
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})
        self._setup_main_phase(game, 0)

        # With only {R} in the pool, the cast can only succeed if the {3}
        # generic was reduced to {0} by the granted affinity (3 creatures).
        engine_cast_spell(game, p1, bolt)

        assert any(
            getattr(so, "source", None) is bolt for so in game.stack.objects()
        )
        assert p1.mana_pool.get(ManaType.RED) == 0
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_controllers_sorcery_gets_affinity_reduction(self) -> None:
        """Granted affinity also reduces a sorcery. {4}{U} with 2 creatures in
        play (Witherbloom + 1) reduces {4} to {2}; pay {2}{U} exactly."""
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = _make_creature("Bear A", owner=p1)
        div = _make_sorcery("Affinity Divination", cost="{4}{U}", owner=p1)
        set_board_state(game, 0, battlefield=[dragon, c1])
        set_board_state(
            game,
            0,
            hand=[div],
            mana={ManaType.COLORLESS: 2, ManaType.BLUE: 1},
        )
        self._setup_main_phase(game, 0)

        engine_cast_spell(game, p1, div)

        assert any(
            getattr(so, "source", None) is div for so in game.stack.objects()
        )
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        assert p1.mana_pool.get(ManaType.BLUE) == 0

    def test_granted_affinity_does_not_reduce_creature_spells(self) -> None:
        """The grant applies only to instants/sorceries. A creature spell cast
        while Witherbloom is in play gets no affinity reduction — a {3}{G}
        creature still needs its full {3}{G} and cannot be cast with only {G}.
        """
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = _make_creature("Bear A", owner=p1)
        c2 = _make_creature("Bear B", owner=p1)
        big_bear = Creature(
            name="Big Bear",
            mana_cost=ManaCost.parse("{3}{G}"),
            base_power=4,
            base_toughness=4,
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[dragon, c1, c2])
        set_board_state(game, 0, hand=[big_bear], mana={ManaType.GREEN: 1})
        self._setup_main_phase(game, 0)

        from engine.casting import CastingError

        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, big_bear)
        # Nothing was cast and the mana is untouched.
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.GREEN) == 1

    def test_no_grant_without_witherbloom_in_play(self) -> None:
        """Regression: with Witherbloom NOT on the battlefield, a {3}{R} instant
        is NOT reduced even though the controller has creatures — affinity is
        granted only by Witherbloom being in play."""
        game = create_game()
        p1 = game.players[0]
        c1 = _make_creature("Bear A", owner=p1)
        c2 = _make_creature("Bear B", owner=p1)
        c3 = _make_creature("Bear C", owner=p1)
        bolt = _make_instant("Plain Bolt", cost="{3}{R}", owner=p1)
        set_board_state(game, 0, battlefield=[c1, c2, c3])
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})
        self._setup_main_phase(game, 0)

        from engine.casting import CastingError

        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, bolt)
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.RED) == 1
