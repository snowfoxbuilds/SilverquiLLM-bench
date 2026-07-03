"""Tests for SOS 167 — Wild Hypothesis."""

from __future__ import annotations

import pytest

from cards.sos.sos_167.card_impl import WildHypothesis
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestWildHypothesisProperties:
    """Static card data should match the SOS 167 spec."""

    def test_name(self) -> None:
        card = WildHypothesis(owner=None)
        assert card.name == "Wild Hypothesis"

    def test_is_sorcery(self) -> None:
        card = WildHypothesis(owner=None)
        assert isinstance(card, Sorcery)

    def test_mana_cost(self) -> None:
        card = WildHypothesis(owner=None)
        assert card.mana_cost == ManaCost.parse("{X}{G}")


class TestWildHypothesisResolution:
    """Wild Hypothesis creates a Fractal token with X +1/+1 counters, then surveils 2."""

    def test_creates_fractal_token(self) -> None:
        """Should create a 0/0 green and blue Fractal creature token."""
        game = create_game()
        p1 = game.players[0]
        card = WildHypothesis(owner=p1, controller=p1)
        card.x_value = 3
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.cards if hasattr(c, 'is_token') and c.is_token]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.base_power == 0
        assert token.base_toughness == 0
        assert "Fractal" in token.subtypes

    def test_fractal_gets_x_counters(self) -> None:
        """The Fractal token should get X +1/+1 counters."""
        game = create_game()
        p1 = game.players[0]
        card = WildHypothesis(owner=p1, controller=p1)
        card.x_value = 5
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.cards if hasattr(c, 'is_token') and c.is_token]
        assert tokens[0].plus_one_counters == 5

    def test_x_equals_zero_creates_zero_zero_fractal(self) -> None:
        """With X=0, still creates a 0/0 token with no counters."""
        game = create_game()
        p1 = game.players[0]
        card = WildHypothesis(owner=p1, controller=p1)
        card.x_value = 0
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.cards if hasattr(c, 'is_token') and c.is_token]
        assert len(tokens) == 1
        assert tokens[0].plus_one_counters == 0

    def test_surveil_two_after_token(self) -> None:
        """After creating the token, surveil 2."""
        game = create_game()
        p1 = game.players[0]
        # Put cards on top of library for surveil
        filler1 = Creature(name="Filler1", owner=p1, base_power=1, base_toughness=1)
        filler2 = Creature(name="Filler2", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).add_top(filler1)
        game.get_library(p1).add_top(filler2)
        card = WildHypothesis(owner=p1, controller=p1)
        card.x_value = 1
        # Configure surveil choices to put both into graveyard
        p1.surveil_choices = [True, True]
        card.on_resolve(game)
        gy = game.get_graveyard(p1)
        # Both surveiled cards should be in graveyard
        assert filler1 in gy.cards or filler2 in gy.cards

    def test_fractal_is_green_and_blue(self) -> None:
        """The token should be green and blue."""
        game = create_game()
        p1 = game.players[0]
        card = WildHypothesis(owner=p1, controller=p1)
        card.x_value = 2
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.cards if hasattr(c, 'is_token') and c.is_token]
        token = tokens[0]
        assert "G" in token.colors
        assert "U" in token.colors
