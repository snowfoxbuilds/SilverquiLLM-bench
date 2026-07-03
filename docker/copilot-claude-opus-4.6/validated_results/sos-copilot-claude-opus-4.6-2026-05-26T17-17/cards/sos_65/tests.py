"""Tests for SOS 65 — Quick Study.

An instant for {2}{U} that draws two cards.
"""

from __future__ import annotations

from cards.sos.sos_65.card_impl import QuickStudy
from engine.card import Instant
from engine.types import (
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestQuickStudyProperties:
    """Static card data should match the SOS 65 spec."""

    def test_is_instant(self) -> None:
        card = QuickStudy(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert QuickStudy(owner=None).name == "Quick Study"

    def test_mana_cost(self) -> None:
        assert QuickStudy(owner=None).mana_cost == ManaCost.parse("{2}{U}")


class TestQuickStudyResolution:
    """on_resolve draws two cards for the controller."""

    def test_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Give player a library to draw from
        from engine.card import Card
        for i in range(5):
            game.get_library(p1).append(Card(name=f"Filler{i}", owner=p1))
        hand_before = len(game.get_hand(p1))
        spell = QuickStudy(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand_after = len(game.get_hand(p1))
        assert hand_after == hand_before + 2

    def test_draws_from_library(self) -> None:
        """Cards drawn should come from the top of the library."""
        game = create_game()
        p1 = game.players[0]
        from engine.card import Card
        cards_in_lib = [Card(name=f"LibCard{i}", owner=p1) for i in range(5)]
        for c in cards_in_lib:
            game.get_library(p1).append(c)
        lib_before = len(game.get_library(p1))
        spell = QuickStudy(owner=p1, controller=p1)
        spell.on_resolve(game)
        lib_after = len(game.get_library(p1))
        assert lib_after == lib_before - 2

    def test_no_targets_required(self) -> None:
        """Quick Study has no targets."""
        game = create_game()
        card = QuickStudy(owner=None)
        targets = card.get_targets(game)
        assert targets is None or targets == []
