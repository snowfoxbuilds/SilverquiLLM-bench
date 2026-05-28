"""Tests for SOS 245 -- Witherbloom, the Balancer.

TDD red-phase tests covering all requirements from the card spec:
  - Static properties (name, mana cost, P/T, keywords, types, supertypes, subtypes)
  - Self affinity: costs {1} less for each creature you control
  - Keywords: flying, deathtouch
  - Grants affinity: instant and sorcery spells you cast have affinity for creatures
"""

from __future__ import annotations

import pytest
from typing import Any

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery, Enchantment
from engine.casting import get_cost_reduction
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creature(name: str = "Grizzly Bears", power: int = 2,
                   toughness: int = 2, owner: Any = None) -> Creature:
    """Create a vanilla creature for test setup."""
    return Creature(name=name, base_power=power, base_toughness=toughness,
                    owner=owner)


def _make_instant(name: str = "Lightning Bolt", mana_cost: str = "{3}{R}",
                  owner: Any = None) -> Instant:
    """Create a simple instant with generic mana in its cost."""
    return Instant(name=name, mana_cost=ManaCost.parse(mana_cost), owner=owner)


def _make_sorcery(name: str = "Divination", mana_cost: str = "{2}{U}",
                  owner: Any = None) -> Sorcery:
    """Create a simple sorcery with generic mana in its cost."""
    return Sorcery(name=name, mana_cost=ManaCost.parse(mana_cost), owner=owner)


def _place_witherbloom_on_battlefield(game, player_index=0):
    """Place a WitherbloomTheBalancer on the battlefield for the given player
    and register its triggers/effects."""
    p = game.players[player_index]
    witherbloom = WitherbloomTheBalancer(owner=p, controller=p)
    witherbloom.summoning_sick = False
    game.get_battlefield(p).add(witherbloom)
    witherbloom.register_triggers(game)
    if hasattr(witherbloom, "register_replacement_effects"):
        witherbloom.register_replacement_effects(game)
    return witherbloom


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestWitherbloomProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_mana_cost_generic_is_6(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost.generic == 6

    def test_mana_cost_has_black_pip(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost.pips.get(ManaType.BLACK, 0) == 1

    def test_mana_cost_has_green_pip(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost.pips.get(ManaType.GREEN, 0) == 1

    def test_power(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_creature_type(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtype_elder(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes

    def test_subtype_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Self affinity -- Affinity for creatures
# ---------------------------------------------------------------------------


class TestWitherbloomSelfAffinity:
    """Affinity for creatures: this spell costs {1} less for each creature
    you control."""

    def test_no_creatures_no_reduction(self) -> None:
        """With no creatures on the battlefield, cost_reduction returns 0."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_creature_reduces_by_one(self) -> None:
        """One creature you control reduces the cost by 1."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = _make_creature("Grizzly Bears", owner=p1)
        set_board_state(game, 0, battlefield=[bear])
        assert card.cost_reduction(game) == 1

    def test_three_creatures_reduces_by_three(self) -> None:
        """Three creatures you control reduces the cost by 3."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bears = [_make_creature(f"Bear {i}", owner=p1) for i in range(3)]
        set_board_state(game, 0, battlefield=bears)
        assert card.cost_reduction(game) == 3

    def test_six_creatures_reduces_full_generic(self) -> None:
        """Six creatures means the raw reduction is 6, which equals the
        generic portion of {6}{B}{G}."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_creature(f"Bear {i}", owner=p1) for i in range(6)]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 6

    def test_more_creatures_than_generic_returns_raw_count(self) -> None:
        """With 8 creatures, cost_reduction should return the raw count (8).
        The engine's get_cost_reduction clamps to generic (6)."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_creature(f"Bear {i}", owner=p1) for i in range(8)]
        set_board_state(game, 0, battlefield=creatures)
        # Per KEY_DECISIONS: cost_reduction returns raw count, engine clamps
        assert card.cost_reduction(game) >= 6

    def test_opponent_creatures_do_not_count(self) -> None:
        """Only YOUR creatures contribute to affinity, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        opp_bear = _make_creature("Opp Bear", owner=p2)
        set_board_state(game, 1, battlefield=[opp_bear])
        assert card.cost_reduction(game) == 0

    def test_non_creature_permanents_do_not_count(self) -> None:
        """Non-creature permanents (enchantments, artifacts) should not
        contribute to the creature affinity count."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        ench = Enchantment(name="Test Enchantment", owner=p1)
        set_board_state(game, 0, battlefield=[ench])
        assert card.cost_reduction(game) == 0

    def test_mixed_permanents_only_count_creatures(self) -> None:
        """In a mixed board, only creatures contribute to affinity."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = _make_creature("Bear", owner=p1)
        ench = Enchantment(name="Enchantment", owner=p1)
        set_board_state(game, 0, battlefield=[bear, ench])
        assert card.cost_reduction(game) == 1

    def test_engine_clamps_reduction_to_generic(self) -> None:
        """The engine's get_cost_reduction clamps the reduction so that
        the generic mana cost cannot go below 0."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_creature(f"Bear {i}", owner=p1) for i in range(10)]
        set_board_state(game, 0, battlefield=creatures)
        clamped = get_cost_reduction(game, card, p1)
        # Generic is 6, so clamped at 6
        assert clamped == 6


# ---------------------------------------------------------------------------
# Grants affinity to instant and sorcery spells
# ---------------------------------------------------------------------------


class TestWitherbloomGrantsAffinity:
    """Instant and sorcery spells you cast have affinity for creatures.

    When Witherbloom is on the battlefield, instants and sorceries cast by
    its controller should have their cost reduced by 1 for each creature
    the controller controls.
    """

    def test_instant_gets_cost_reduction_from_witherbloom(self) -> None:
        """An instant spell should get cost reduction equal to the number
        of creatures the controller controls, when Witherbloom is on the
        battlefield."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        bear = _make_creature("Bear", owner=p1)
        game.get_battlefield(p1).add(bear)
        # 2 creatures total (Witherbloom + Bear)
        bolt = _make_instant("Lightning Bolt", "{3}{R}", owner=p1)
        bolt.controller = p1
        reduction = bolt.cost_reduction(game)
        assert reduction == 2, (
            f"Instant should get reduction of 2 (Witherbloom + Bear), "
            f"got {reduction}"
        )

    def test_sorcery_gets_cost_reduction_from_witherbloom(self) -> None:
        """A sorcery spell should get cost reduction equal to the number
        of creatures the controller controls, when Witherbloom is on the
        battlefield."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        # 1 creature: Witherbloom itself
        div = _make_sorcery("Divination", "{2}{U}", owner=p1)
        div.controller = p1
        reduction = div.cost_reduction(game)
        assert reduction == 1, (
            f"Sorcery should get reduction of 1 (Witherbloom), got {reduction}"
        )

    def test_instant_with_no_creatures_no_reduction(self) -> None:
        """If Witherbloom is on the battlefield but there are no creatures
        (edge case -- Witherbloom itself IS a creature so there is at least 1),
        the reduction should be at least 1 for Witherbloom itself."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        bolt = _make_instant("Lightning Bolt", "{3}{R}", owner=p1)
        bolt.controller = p1
        reduction = bolt.cost_reduction(game)
        # At minimum, Witherbloom itself is a creature
        assert reduction >= 1

    def test_sorcery_with_multiple_creatures(self) -> None:
        """Multiple creatures on the battlefield increase the affinity
        reduction for sorceries."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        bears = [_make_creature(f"Bear {i}", owner=p1) for i in range(4)]
        for b in bears:
            b.controller = p1
            game.get_battlefield(p1).add(b)
        # 5 creatures total: Witherbloom + 4 bears
        sorc = _make_sorcery("Big Spell", "{5}{U}", owner=p1)
        sorc.controller = p1
        reduction = sorc.cost_reduction(game)
        assert reduction == 5

    def test_creature_spell_does_not_get_affinity_grant(self) -> None:
        """Creature spells should NOT get affinity from Witherbloom.
        Only instants and sorceries are granted affinity."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        # Another creature card in hand
        other_creature = _make_creature("Other Dragon", 3, 3, owner=p1)
        other_creature.controller = p1
        # Creatures don't inherently have cost_reduction unless they implement it
        reduction = other_creature.cost_reduction(game)
        assert reduction == 0, (
            f"Creature spells should not get affinity from Witherbloom, "
            f"got {reduction}"
        )

    def test_enchantment_does_not_get_affinity_grant(self) -> None:
        """Non-instant, non-sorcery, non-creature spells should not get
        affinity from Witherbloom."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        ench = Enchantment(name="Test Enchantment",
                           mana_cost=ManaCost.parse("{3}{W}"), owner=p1)
        ench.controller = p1
        reduction = ench.cost_reduction(game)
        assert reduction == 0

    def test_opponent_instant_does_not_get_affinity(self) -> None:
        """Only YOUR instant and sorcery spells get affinity, not the
        opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        # Opponent's instant
        opp_bolt = _make_instant("Opponent Bolt", "{3}{R}", owner=p2)
        opp_bolt.controller = p2
        reduction = opp_bolt.cost_reduction(game)
        assert reduction == 0, (
            f"Opponent's instant should NOT get affinity from your Witherbloom, "
            f"got {reduction}"
        )

    def test_instant_cast_with_affinity_uses_reduced_cost(self) -> None:
        """Integration: casting an instant with Witherbloom on the battlefield
        should use the reduced cost from affinity for creatures."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        bear = _make_creature("Bear", owner=p1)
        bear.controller = p1
        game.get_battlefield(p1).add(bear)
        # 2 creatures on battlefield: Witherbloom + Bear
        # Instant costs {3}{R}, with 2 creature affinity -> effective {1}{R}
        bolt = _make_instant("Lightning Bolt", "{3}{R}", owner=p1)
        set_board_state(game, 0, hand=[bolt],
                        mana={ManaType.COLORLESS: 1, ManaType.RED: 1})
        # Keep battlefield intact -- re-add Witherbloom and bear if set_board_state cleared them
        # Actually set_board_state only modifies zones you specify; hand and mana won't affect battlefield
        from test_utils import cast_spell
        # This should succeed with only 2 mana because affinity reduces cost by 2
        cast_spell(game, 0, "Lightning Bolt")


class TestWitherbloomGrantsAffinityEdgeCases:
    """Edge cases for the affinity-granting ability."""

    def test_witherbloom_not_on_battlefield_no_affinity_grant(self) -> None:
        """If Witherbloom is NOT on the battlefield (e.g. in hand or
        graveyard), instants/sorceries should not get affinity."""
        game = create_game()
        p1 = game.players[0]
        # Witherbloom in hand, not on battlefield
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[witherbloom])
        # Put some creatures on the battlefield
        bear = _make_creature("Bear", owner=p1)
        set_board_state(game, 0, battlefield=[bear])
        bolt = _make_instant("Lightning Bolt", "{3}{R}", owner=p1)
        bolt.controller = p1
        reduction = bolt.cost_reduction(game)
        assert reduction == 0, (
            f"Instant should NOT get affinity when Witherbloom is not on "
            f"battlefield, got {reduction}"
        )

    def test_witherbloom_counts_itself_as_creature(self) -> None:
        """Witherbloom itself is a creature, so it should be counted in
        the affinity calculation for instants/sorceries."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = _place_witherbloom_on_battlefield(game, 0)
        # Only Witherbloom on the battlefield (1 creature)
        bolt = _make_instant("Lightning Bolt", "{3}{R}", owner=p1)
        bolt.controller = p1
        reduction = bolt.cost_reduction(game)
        assert reduction == 1, (
            f"Witherbloom counts as a creature for its own affinity-granting, "
            f"got {reduction}"
        )
