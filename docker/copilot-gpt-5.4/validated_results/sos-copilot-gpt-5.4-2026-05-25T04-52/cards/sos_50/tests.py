"""Tests for SOS 50 — Fractal Anomaly."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_50.card_impl import FractalAnomaly
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFractalAnomalyProperties:
    """Static card data should match the SOS 50 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(FractalAnomaly(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = FractalAnomaly(owner=None)
        assert card.name == "Fractal Anomaly"
        assert card.mana_cost == ManaCost.parse("{U}")


class TestFractalAnomalyResolution:
    """Fractal Anomaly should create a Fractal token sized by cards drawn this turn."""

    def test_creates_a_green_and_blue_fractal_token_with_counters_equal_to_cards_you_drew_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        draw_one = CardImpl(name="First Draw", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Draw", owner=p1, controller=p1)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        draw_card(game, p1)
        draw_card(game, p1)

        card = FractalAnomaly(owner=p1, controller=p1)
        card.on_resolve(game)

        tokens = game.get_battlefield(p1).get_all()
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert "Fractal" in token.subtypes
        assert get_colors(token) == {Color.GREEN, Color.BLUE}
        assert token.plus_one_counters == 2
        assert token.power == 2
        assert token.toughness == 2

    def test_uses_your_draw_count_not_an_opponents(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.get_library(p2).add(CardImpl(name="Opposing Draw", owner=p2, controller=p2))
        draw_card(game, p2)

        card = FractalAnomaly(owner=p1, controller=p1)
        card.on_resolve(game)

        tokens = game.get_battlefield(p1).get_all()
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.plus_one_counters == 0
        assert token.power == 0
        assert token.toughness == 0
