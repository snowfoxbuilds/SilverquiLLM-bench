"""Tests for SOS 62 — Orysa, Tide Choreographer.

A legendary 2/2 Merfolk Bard for {4}{U} that costs {3} less if your creatures
have total toughness 10+. When it enters, draw two cards.
"""

from __future__ import annotations

from cards.sos.sos_62.card_impl import OrysaTideChoreographer
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestOrysaProperties:
    """Static card data should match the SOS 62 spec."""

    def test_is_creature(self) -> None:
        card = OrysaTideChoreographer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert OrysaTideChoreographer(owner=None).name == "Orysa, Tide Choreographer"

    def test_mana_cost(self) -> None:
        assert OrysaTideChoreographer(owner=None).mana_cost == ManaCost.parse("{4}{U}")

    def test_power_toughness(self) -> None:
        card = OrysaTideChoreographer(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_is_legendary(self) -> None:
        card = OrysaTideChoreographer(owner=None)
        assert card.legendary is True or "Legendary" in getattr(card, 'supertypes', set())


class TestOrysaCostReduction:
    """Cost reduction when creatures you control have total toughness >= 10."""

    def test_no_reduction_with_low_toughness(self) -> None:
        """With total toughness < 10, cost should be full {4}{U}."""
        game = create_game()
        p1 = game.players[0]
        # One 2/2 creature: total toughness = 2
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[bear])
        card = OrysaTideChoreographer(owner=p1, controller=p1)
        cost = card.get_effective_cost(game)
        # Full cost: 4 generic + 1 blue = 5 total mana
        assert cost.total() == 5

    def test_reduction_with_toughness_10_or_more(self) -> None:
        """With total toughness >= 10, cost should be {1}{U} (3 less)."""
        game = create_game()
        p1 = game.players[0]
        # Creatures with total toughness = 12
        c1 = Creature(name="Big1", owner=p1, controller=p1, base_power=1, base_toughness=6)
        c2 = Creature(name="Big2", owner=p1, controller=p1, base_power=1, base_toughness=6)
        set_board_state(game, 0, battlefield=[c1, c2])
        card = OrysaTideChoreographer(owner=p1, controller=p1)
        cost = card.get_effective_cost(game)
        # Reduced cost: {1}{U} = 2 total
        assert cost.total() == 2

    def test_reduction_exactly_10_toughness(self) -> None:
        """Total toughness == 10 should trigger the reduction."""
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Big1", owner=p1, controller=p1, base_power=1, base_toughness=5)
        c2 = Creature(name="Big2", owner=p1, controller=p1, base_power=1, base_toughness=5)
        set_board_state(game, 0, battlefield=[c1, c2])
        card = OrysaTideChoreographer(owner=p1, controller=p1)
        cost = card.get_effective_cost(game)
        assert cost.total() == 2


class TestOrysaETB:
    """When Orysa enters the battlefield, draw two cards."""

    def test_draws_two_cards_on_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Give player a library to draw from
        from engine.card import Card
        for i in range(5):
            game.get_library(p1).append(Card(name=f"Filler{i}", owner=p1))
        hand_before = len(game.get_hand(p1))
        card = OrysaTideChoreographer(owner=p1, controller=p1)
        card.on_enter_battlefield(game)
        hand_after = len(game.get_hand(p1))
        assert hand_after == hand_before + 2
