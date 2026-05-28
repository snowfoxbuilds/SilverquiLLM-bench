"""Audited tests for SOS 1 — The Dawning Archaic.

Rewritten tests covering:
- Identity (name, cost, CMC, types, supertypes, keywords, P/T, colors)
- Cost reduction with graveyard instant/sorcery
- Attack trigger decline path (may choice declined → no cast)
- Attack trigger accept path (may choice accepted → spell cast from GY)
- Exile replacement on resolve (cast spell ends up in exile, not GY)
- Scope not global (only chosen card gets exile replacement)

Bug pattern addressed: "may" treated as mandatory (general issue #5).

All tests use canonical engine APIs (declare_attackers, resolve_top) — no
private method calls or hand-constructed internal events.
"""

from __future__ import annotations

from card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import (
    assert_in_zone,
    assert_on_stack,
    create_game,
    declare_attackers,
    resolve_top,
    set_battlefield,
    set_graveyard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instant(name: str = "Lightning Bolt") -> Instant:
    """Create a simple instant card for testing."""
    return Instant(name=name)


def _make_sorcery(name: str = "Divination") -> Sorcery:
    """Create a simple sorcery card for testing."""
    return Sorcery(name=name)


def _setup_attack_scenario(
    *,
    gy_cards: list,
    scripts: tuple[list, list],
) -> tuple:
    """Set up a game where The Dawning Archaic is about to attack.

    Returns (game, card, p1) after declaring attackers and putting the
    attack trigger on the stack (but NOT yet resolving it).
    """
    game = create_game(scripts=scripts)
    p1 = game.players[0]
    card = TheDawningArchaic(owner=p1, controller=p1)
    set_battlefield(game, 0, [card])
    set_graveyard(game, 0, gy_cards)

    # Enter combat and declare The Dawning Archaic as attacker.
    # This should put the attack trigger on the stack.
    declare_attackers(game, ["The Dawning Archaic"])

    return game, card, p1


# ---------------------------------------------------------------------------
# Test 1: Identity
# ---------------------------------------------------------------------------


class TestTheDawningArchaicIdentity:
    """Verify static card properties match the card spec."""

    def test_name(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost(generic=10)

    def test_cmc(self) -> None:
        card = TheDawningArchaic(owner=None)
        # CMC of {10} is 10
        cmc = getattr(card.mana_cost, "cmc", None)
        if cmc is None:
            # Fallback: compute from generic
            cmc = card.mana_cost.generic
        assert cmc == 10

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_legendary_supertype(self) -> None:
        """The Dawning Archaic is Legendary."""
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_reach_keyword(self) -> None:
        """The Dawning Archaic has Reach."""
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_colorless(self) -> None:
        """The Dawning Archaic has mana cost {10} — no colors."""
        card = TheDawningArchaic(owner=None)
        # The card should have no colors (colorless)
        colors = getattr(card, "colors", None)
        if colors is not None:
            assert len(colors) == 0
        else:
            # Derive from mana cost — {10} has no colored pips
            from test_utils import card_colors
            assert card_colors(card) == set()


# ---------------------------------------------------------------------------
# Test 2: Cost reduction with graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """Cost reduction equals count of instant/sorcery in controller's GY."""

    def test_no_instants_or_sorceries_in_gy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_battlefield(game, 0, [card])
        # Empty graveyard → no reduction
        assert card.cost_reduction(game) == 0

    def test_counts_instants_in_gy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_battlefield(game, 0, [card])
        bolt = _make_instant("Lightning Bolt")
        shock = _make_instant("Shock")
        set_graveyard(game, 0, [bolt, shock])
        assert card.cost_reduction(game) == 2

    def test_counts_sorceries_in_gy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_battlefield(game, 0, [card])
        div = _make_sorcery("Divination")
        set_graveyard(game, 0, [div])
        assert card.cost_reduction(game) == 1

    def test_does_not_count_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_battlefield(game, 0, [card])
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        bolt = _make_instant("Lightning Bolt")
        set_graveyard(game, 0, [creature, bolt])
        # Only 1 instant, creature doesn't count
        assert card.cost_reduction(game) == 1


# ---------------------------------------------------------------------------
# Test 3: Attack trigger — decline path
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTriggerDecline:
    """When 'may' choice is declined, no spell is cast from the graveyard."""

    def test_decline_does_not_cast_from_gy(self) -> None:
        """Declining the may trigger leaves the graveyard unchanged."""
        bolt = _make_instant("Lightning Bolt")
        game, card, p1 = _setup_attack_scenario(
            gy_cards=[bolt],
            scripts=([False], []),  # Player 1 script: decline may choice
        )

        # Resolve the attack trigger on the stack
        resolve_top(game)

        # Bolt should still be in graveyard — nothing was cast
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Lightning Bolt")

    def test_decline_leaves_stack_empty(self) -> None:
        """Declining the may trigger leaves the stack empty after resolution."""
        bolt = _make_instant("Lightning Bolt")
        game, card, p1 = _setup_attack_scenario(
            gy_cards=[bolt],
            scripts=([False], []),
        )

        # Resolve the attack trigger
        resolve_top(game)

        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Test 4: Attack trigger — accept path
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTriggerAccept:
    """When 'may' choice is accepted, a spell is cast from the graveyard."""

    def test_accept_casts_spell_from_gy(self) -> None:
        """Accepting the may trigger removes the chosen spell from the GY."""
        bolt = _make_instant("Lightning Bolt")
        game, card, p1 = _setup_attack_scenario(
            gy_cards=[bolt],
            scripts=([True, bolt], []),  # Accept + choose bolt
        )

        # Resolve the attack trigger — this casts bolt from GY
        resolve_top(game)

        # Bolt should no longer be in the graveyard (it was cast)
        gy_cards = p1.zones[Zone.GRAVEYARD].get_all()
        gy_names = [getattr(c, "name", "") for c in gy_cards]
        assert "Lightning Bolt" not in gy_names

    def test_accept_spell_resolves_to_exile(self) -> None:
        """The spell cast via the trigger goes to exile (not GY) on resolve."""
        bolt = _make_instant("Lightning Bolt")
        game, card, p1 = _setup_attack_scenario(
            gy_cards=[bolt],
            scripts=([True, bolt], []),
        )

        # Resolve the attack trigger (casts bolt, puts it on stack)
        resolve_top(game)

        # Now resolve the bolt itself — it should end up in exile
        if not game.stack.is_empty():
            resolve_top(game)

        # Bolt should be in exile, not graveyard
        assert_in_zone(game, 0, Zone.EXILE, "Lightning Bolt")

        # Bolt should NOT be in graveyard
        gy_cards = p1.zones[Zone.GRAVEYARD].get_all()
        gy_names = [getattr(c, "name", "") for c in gy_cards]
        assert "Lightning Bolt" not in gy_names


# ---------------------------------------------------------------------------
# Test 5: Exile replacement — sorcery also works
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileSorcery:
    """The exile replacement works for sorceries cast from GY too."""

    def test_sorcery_from_gy_goes_to_exile(self) -> None:
        """A sorcery cast via the attack trigger goes to exile on resolve."""
        div = _make_sorcery("Divination")
        game, card, p1 = _setup_attack_scenario(
            gy_cards=[div],
            scripts=([True, div], []),
        )

        # Resolve the attack trigger (casts Divination)
        resolve_top(game)

        # Resolve Divination itself
        if not game.stack.is_empty():
            resolve_top(game)

        # Should be in exile
        assert_in_zone(game, 0, Zone.EXILE, "Divination")


# ---------------------------------------------------------------------------
# Test 6: Scope — not global
# ---------------------------------------------------------------------------


class TestTheDawningArchaicScopeNotGlobal:
    """The exile replacement only applies to the chosen card, not all spells."""

    def test_other_spells_go_to_graveyard_normally(self) -> None:
        """A different instant/sorcery cast normally still goes to GY."""
        bolt = _make_instant("Lightning Bolt")
        shock = _make_instant("Shock")
        game, card, p1 = _setup_attack_scenario(
            gy_cards=[bolt],
            scripts=([True, bolt], []),
        )

        # Resolve the attack trigger (casts bolt from GY)
        resolve_top(game)

        # Resolve bolt
        if not game.stack.is_empty():
            resolve_top(game)

        # Bolt went to exile
        assert_in_zone(game, 0, Zone.EXILE, "Lightning Bolt")

        # Now cast Shock normally (not via the trigger) — it should go to GY
        from test_utils import set_hand, cast_spell, set_mana_pool
        from engine.types import ManaType

        set_hand(game, 0, [shock])
        set_mana_pool(game, 0, {ManaType.RED: 1})
        cast_spell(game, 0, "Shock")

        # Shock should be in graveyard, not exile
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Shock")


# ---------------------------------------------------------------------------
# Test 7: Attack trigger — multiple instants/sorceries in GY
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTargeting:
    """The trigger targets a specific instant/sorcery — only that one is exiled."""

    def test_only_chosen_card_is_exiled(self) -> None:
        """When multiple spells are in GY, only the chosen target is exiled."""
        bolt = _make_instant("Lightning Bolt")
        shock = _make_instant("Shock")
        game, card, p1 = _setup_attack_scenario(
            gy_cards=[bolt, shock],
            scripts=([True, bolt], []),  # Choose bolt
        )

        # Resolve trigger + bolt
        resolve_top(game)
        if not game.stack.is_empty():
            resolve_top(game)

        # Bolt exiled, Shock still in GY
        assert_in_zone(game, 0, Zone.EXILE, "Lightning Bolt")
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Shock")
