"""Tests for SOS 70 — Textbook Tabulator.

A {2}{U} 0/3 Frog Wizard with Increment and an ETB surveil 2.
"""

from __future__ import annotations

from cards.sos.sos_70.card_impl import TextbookTabulator
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestTextbookTabulatorProperties:
    """Static card data should match the SOS 70 spec."""

    def test_is_creature(self) -> None:
        card = TextbookTabulator(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TextbookTabulator(owner=None)
        assert card.name == "Textbook Tabulator"

    def test_mana_cost(self) -> None:
        card = TextbookTabulator(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")

    def test_power_toughness(self) -> None:
        card = TextbookTabulator(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 3

    def test_has_increment(self) -> None:
        card = TextbookTabulator(owner=None)
        assert Keyword.INCREMENT in card.keywords

    def test_has_surveil(self) -> None:
        card = TextbookTabulator(owner=None)
        assert Keyword.SURVEIL in card.keywords


class TestTextbookTabulatorIncrement:
    """Increment: gains +1/+1 counter when mana spent on spell > power or toughness."""

    def test_increment_triggers_when_mana_exceeds_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TextbookTabulator(owner=p1, controller=p1)
        card.plus_one_counters = 0
        game.get_battlefield(p1).add(card)
        # Power is 0, so any mana > 0 should trigger
        card.on_increment_trigger(game, mana_spent=1)
        assert card.plus_one_counters == 1

    def test_increment_does_not_trigger_when_mana_not_greater(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TextbookTabulator(owner=p1, controller=p1)
        card.plus_one_counters = 0
        game.get_battlefield(p1).add(card)
        # Power is 0, toughness is 3; mana_spent=0 not greater than either
        card.on_increment_trigger(game, mana_spent=0)
        assert card.plus_one_counters == 0

    def test_increment_triggers_when_mana_exceeds_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TextbookTabulator(owner=p1, controller=p1)
        card.plus_one_counters = 0
        game.get_battlefield(p1).add(card)
        # Toughness is 3; mana_spent=4 exceeds it
        card.on_increment_trigger(game, mana_spent=4)
        assert card.plus_one_counters == 1


class TestTextbookTabulatorETB:
    """When this creature enters, surveil 2."""

    def test_surveil_on_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Set up library with known cards
        card1 = Creature(name="Card A", owner=p1, base_power=1, base_toughness=1)
        card2 = Creature(name="Card B", owner=p1, base_power=1, base_toughness=1)
        card3 = Creature(name="Card C", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[], mana={ManaType.BLUE: 3, ManaType.COLORLESS: 2})
        library = game.get_library(p1)
        library.add(card1)
        library.add(card2)
        library.add(card3)

        tabulator = TextbookTabulator(owner=p1, controller=p1)
        initial_library_size = len(library.get_all())
        tabulator.on_resolve(game)

        # After surveil 2, player should have looked at top 2 cards
        # Total cards in library + graveyard should remain consistent
        final_library = len(game.get_library(p1).get_all())
        final_graveyard = len(game.get_graveyard(p1).get_all())
        # The 2 surveilled cards are either in library or graveyard
        assert final_library + final_graveyard == initial_library_size

    def test_surveil_with_empty_library(self) -> None:
        """Surveil with fewer than 2 cards should not error."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, hand=[])
        # Empty library — surveil should handle gracefully
        tabulator = TextbookTabulator(owner=p1, controller=p1)
        tabulator.on_resolve(game)  # Should not raise
