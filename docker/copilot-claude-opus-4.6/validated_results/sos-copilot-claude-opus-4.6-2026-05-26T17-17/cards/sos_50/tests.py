"""Tests for SOS 50 — Fractal Anomaly.

Instant for {U}.
Create a 0/0 green and blue Fractal creature token and put X +1/+1 counters
on it, where X is the number of cards you've drawn this turn.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_50.card_impl import FractalAnomaly
from engine.card import Instant, Creature
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestFractalAnomalyProperties:
    """Static card data should match the SOS 50 spec."""

    def test_is_instant(self) -> None:
        card = FractalAnomaly(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = FractalAnomaly(owner=None)
        assert card.name == "Fractal Anomaly"

    def test_mana_cost(self) -> None:
        card = FractalAnomaly(owner=None)
        assert card.mana_cost == ManaCost.parse("{U}")


class TestFractalAnomalyToken:
    """Creates a 0/0 Fractal token with +1/+1 counters equal to cards drawn."""

    def test_creates_token_on_battlefield(self) -> None:
        """Resolving should create a creature token on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        spell = FractalAnomaly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fractal Anomaly")
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) >= 1

    def test_token_is_0_0_base(self) -> None:
        """The Fractal token has base 0/0."""
        game = create_game()
        p1 = game.players[0]
        spell = FractalAnomaly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fractal Anomaly")
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        token = tokens[0]
        assert token.base_power == 0
        assert token.base_toughness == 0

    def test_token_is_green_and_blue(self) -> None:
        """The token should be green and blue."""
        game = create_game()
        p1 = game.players[0]
        spell = FractalAnomaly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fractal Anomaly")
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        token = tokens[0]
        from engine.types import Color
        assert Color.GREEN in token.colors
        assert Color.BLUE in token.colors

    def test_token_is_fractal_creature(self) -> None:
        """The token should be a Fractal creature."""
        game = create_game()
        p1 = game.players[0]
        spell = FractalAnomaly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fractal Anomaly")
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        token = tokens[0]
        assert isinstance(token, Creature)
        assert "Fractal" in getattr(token, "subtypes", set())

    def test_zero_cards_drawn_means_zero_counters(self) -> None:
        """If no cards drawn this turn, X=0, no counters."""
        game = create_game()
        p1 = game.players[0]
        p1.cards_drawn_this_turn = 0
        spell = FractalAnomaly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fractal Anomaly")
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        token = tokens[0]
        counters = getattr(token, "counters", {}).get("+1/+1", 0)
        assert counters == 0

    def test_three_cards_drawn_means_three_counters(self) -> None:
        """If 3 cards drawn this turn, token gets 3 +1/+1 counters."""
        game = create_game()
        p1 = game.players[0]
        p1.cards_drawn_this_turn = 3
        spell = FractalAnomaly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fractal Anomaly")
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        token = tokens[0]
        counters = getattr(token, "counters", {}).get("+1/+1", 0)
        assert counters == 3

    def test_token_effective_pt_with_counters(self) -> None:
        """Token with 2 counters should be effectively 2/2."""
        game = create_game()
        p1 = game.players[0]
        p1.cards_drawn_this_turn = 2
        spell = FractalAnomaly(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Fractal Anomaly")
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        token = tokens[0]
        assert token.power == 2
        assert token.toughness == 2
