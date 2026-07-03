"""Tests for SOS 63 — Pensive Professor.

A 0/2 Creature — Human Wizard for {1}{U}{U} with Increment and a triggered
ability that draws a card whenever one or more +1/+1 counters are put on it.
"""

from __future__ import annotations

from cards.sos.sos_63.card_impl import PensiveProfessor
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestPensiveProfessorProperties:
    """Static card data should match the SOS 63 spec."""

    def test_is_creature(self) -> None:
        card = PensiveProfessor(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert PensiveProfessor(owner=None).name == "Pensive Professor"

    def test_mana_cost(self) -> None:
        assert PensiveProfessor(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_power_toughness(self) -> None:
        card = PensiveProfessor(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 2

    def test_has_increment_keyword(self) -> None:
        card = PensiveProfessor(owner=None)
        assert Keyword.INCREMENT in card.keywords


class TestPensiveProfessorIncrement:
    """Increment: when you cast a spell with mana spent > power or toughness, +1/+1 counter."""

    def test_increment_triggers_when_mana_exceeds_power(self) -> None:
        """Casting a spell for more mana than power (0) should give a counter."""
        game = create_game()
        p1 = game.players[0]
        prof = PensiveProfessor(owner=p1, controller=p1)
        prof.base_power = 0
        prof.base_toughness = 2
        prof.plus_one_counters = 0
        game.get_battlefield(p1).add(prof)
        # Simulate casting a spell that cost 1 mana (> power 0)
        prof.on_spell_cast(game, mana_spent=1)
        assert prof.plus_one_counters >= 1

    def test_increment_does_not_trigger_when_mana_not_exceeding(self) -> None:
        """Casting a 0-cost spell should not trigger increment on a 0/2."""
        game = create_game()
        p1 = game.players[0]
        prof = PensiveProfessor(owner=p1, controller=p1)
        prof.base_power = 0
        prof.base_toughness = 2
        prof.plus_one_counters = 0
        game.get_battlefield(p1).add(prof)
        # Mana spent = 0, not greater than power (0) or toughness (2)
        prof.on_spell_cast(game, mana_spent=0)
        assert prof.plus_one_counters == 0

    def test_increment_triggers_when_mana_exceeds_toughness(self) -> None:
        """Casting a spell for more mana than toughness (2) should also trigger."""
        game = create_game()
        p1 = game.players[0]
        prof = PensiveProfessor(owner=p1, controller=p1)
        prof.base_power = 0
        prof.base_toughness = 2
        prof.plus_one_counters = 0
        game.get_battlefield(p1).add(prof)
        # Mana spent = 3 > toughness 2
        prof.on_spell_cast(game, mana_spent=3)
        assert prof.plus_one_counters >= 1


class TestPensiveProfessorDrawOnCounter:
    """Whenever +1/+1 counters are put on this creature, draw a card."""

    def test_draws_card_when_counter_added(self) -> None:
        game = create_game()
        p1 = game.players[0]
        prof = PensiveProfessor(owner=p1, controller=p1)
        prof.plus_one_counters = 0
        game.get_battlefield(p1).add(prof)
        # Give library cards to draw from
        from engine.card import Card
        for i in range(5):
            game.get_library(p1).append(Card(name=f"Filler{i}", owner=p1))
        hand_before = len(game.get_hand(p1))
        # Simulate adding a counter (which should trigger draw)
        prof.add_plus_one_counter(game, 1)
        hand_after = len(game.get_hand(p1))
        assert hand_after == hand_before + 1

    def test_draws_one_card_even_with_multiple_counters_at_once(self) -> None:
        """'one or more' means only one draw trigger per batch."""
        game = create_game()
        p1 = game.players[0]
        prof = PensiveProfessor(owner=p1, controller=p1)
        prof.plus_one_counters = 0
        game.get_battlefield(p1).add(prof)
        from engine.card import Card
        for i in range(5):
            game.get_library(p1).append(Card(name=f"Filler{i}", owner=p1))
        hand_before = len(game.get_hand(p1))
        # Add 3 counters at once — should only draw 1 card
        prof.add_plus_one_counter(game, 3)
        hand_after = len(game.get_hand(p1))
        assert hand_after == hand_before + 1
