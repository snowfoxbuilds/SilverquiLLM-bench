"""Tests for SOS 219 — Rapturous Moment.

Rapturous Moment is a {4}{U}{R} Sorcery with:
- Draw three cards, then discard two cards.
- Add {U}{U}{R}{R}{R}.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_219.card_impl import RapturousMoment
from engine.card import Creature
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestRapturousMomentProperties:
    """Static card data should match the SOS 219 spec."""

    def test_name(self) -> None:
        assert RapturousMoment(owner=None).name == "Rapturous Moment"

    def test_mana_cost(self) -> None:
        assert RapturousMoment(owner=None).mana_cost == ManaCost.parse("{4}{U}{R}")


class TestRapturousMomentResolution:
    """on_resolve draws three, discards two, then adds mana."""

    def test_draw_three_cards(self) -> None:
        """Player draws 3 cards as part of resolution."""
        game = create_game(deck1=["A", "B", "C", "D", "E"])
        p1 = game.players[0]
        set_board_state(game, 0, hand=[])
        spell = RapturousMoment(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Drew 3, discarded 2 -> net 1 card in hand
        hand = game.get_hand(p1)
        assert len(hand) == 1

    def test_discard_two_cards(self) -> None:
        """Player discards 2 cards after drawing 3."""
        game = create_game(deck1=["A", "B", "C", "D", "E"])
        p1 = game.players[0]
        set_board_state(game, 0, hand=[])
        spell = RapturousMoment(owner=p1, controller=p1)
        spell.on_resolve(game)
        graveyard = game.get_graveyard(p1)
        # At least 2 cards should be in graveyard from the discards
        assert len(graveyard) >= 2

    def test_adds_mana_uurrrr(self) -> None:
        """Adds {U}{U}{R}{R}{R} to mana pool after draw/discard."""
        game = create_game(deck1=["A", "B", "C", "D", "E"])
        p1 = game.players[0]
        set_board_state(game, 0, hand=[], mana={})
        spell = RapturousMoment(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Should have 2 blue and 3 red mana in pool
        assert p1.mana_pool[ManaType.BLUE] >= 2
        assert p1.mana_pool[ManaType.RED] >= 3

    def test_net_hand_size_with_existing_hand(self) -> None:
        """With existing cards in hand, net change is +1 (draw 3, discard 2)."""
        game = create_game(deck1=["A", "B", "C", "D", "E"])
        p1 = game.players[0]
        filler1 = Creature(name="Filler1", owner=p1, controller=p1, base_power=1, base_toughness=1)
        filler2 = Creature(name="Filler2", owner=p1, controller=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[filler1, filler2])
        spell = RapturousMoment(owner=p1, controller=p1)
        initial_hand_size = 2
        spell.on_resolve(game)
        hand = game.get_hand(p1)
        # Started with 2, drew 3 (=5), discarded 2 (=3)
        assert len(hand) == 3

    def test_mana_added_is_exact(self) -> None:
        """Exactly {U}{U}{R}{R}{R} is added, not more."""
        game = create_game(deck1=["A", "B", "C", "D", "E"])
        p1 = game.players[0]
        set_board_state(game, 0, hand=[], mana={})
        spell = RapturousMoment(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert p1.mana_pool[ManaType.BLUE] == 2
        assert p1.mana_pool[ManaType.RED] == 3
