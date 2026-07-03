"""Tests for SOS 216 — Pursue the Past.

Pursue the Past is a {R}{W} Sorcery with:
- You gain 2 life.
- You may discard a card. If you do, draw two cards.
- Flashback {2}{R}{W}
"""

from __future__ import annotations

import pytest
from cards.sos.sos_216.card_impl import PursueThePast
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state, cast_spell


class TestPursueThePastProperties:
    """Static card data should match the SOS 216 spec."""

    def test_name(self) -> None:
        assert PursueThePast(owner=None).name == "Pursue the Past"

    def test_mana_cost(self) -> None:
        assert PursueThePast(owner=None).mana_cost == ManaCost.parse("{R}{W}")

    def test_has_flashback(self) -> None:
        card = PursueThePast(owner=None)
        assert Keyword.FLASHBACK in card.keywords


class TestPursueThePastResolution:
    """on_resolve effects: gain 2 life, optional discard for draw two."""

    def test_gain_2_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = PursueThePast(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert p1.life == 22

    def test_no_discard_when_hand_empty(self) -> None:
        """If player has no cards in hand, they don't discard and don't draw."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, hand=[])
        spell = PursueThePast(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Still gain life
        assert p1.life == 22
        # No cards drawn (hand still empty since no discard happened)
        hand = game.get_hand(p1)
        assert len(hand) == 0

    def test_discard_then_draw_two(self) -> None:
        """When player chooses to discard, they draw two cards."""
        game = create_game(deck1=["Card A", "Card B", "Card C"])
        p1 = game.players[0]
        filler = Creature(name="Filler", owner=p1, controller=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[filler])
        spell = PursueThePast(owner=p1, controller=p1)
        spell.on_resolve(game)
        # After discarding 1 and drawing 2, hand should have 2 cards
        hand = game.get_hand(p1)
        assert len(hand) == 2

    def test_life_gain_happens_regardless_of_discard(self) -> None:
        """Life gain is not conditional on the discard choice."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, life=10)
        spell = PursueThePast(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert p1.life == 12


class TestPursueThePastFlashback:
    """Flashback allows casting from graveyard for {2}{R}{W}."""

    def test_flashback_cost(self) -> None:
        card = PursueThePast(owner=None)
        assert card.flashback_cost == ManaCost.parse("{2}{R}{W}")

    def test_exiled_after_flashback_resolves(self) -> None:
        """Card is exiled after being cast via flashback."""
        game = create_game(deck1=["Card A", "Card B", "Card C"])
        p1 = game.players[0]
        spell = PursueThePast(owner=p1, controller=p1)
        game.get_graveyard(p1).add(spell)
        set_board_state(game, 0, mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        cast_spell(game, 0, "Pursue the Past")
        # After flashback, card should be in exile
        assert spell.zone == Zone.EXILE
