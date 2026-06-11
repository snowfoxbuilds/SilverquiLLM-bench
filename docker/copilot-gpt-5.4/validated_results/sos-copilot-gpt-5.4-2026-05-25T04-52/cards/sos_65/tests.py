"""Tests for SOS 65 — Quick Study."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_65.card_impl import QuickStudy
from benchmarks.sos.workspace.engine.card import CardImpl, Instant
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestQuickStudyProperties:
    """Static card data should match the SOS 65 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(QuickStudy(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = QuickStudy(owner=None)
        assert card.name == "Quick Study"
        assert card.mana_cost == ManaCost.parse("{2}{U}")


class TestQuickStudyResolution:
    """Quick Study should draw two cards."""

    def test_on_resolve_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        draw_one = CardImpl(name="First Lesson", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Lesson", owner=p1, controller=p1)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        spell = QuickStudy(owner=p1, controller=p1)

        spell.on_resolve(game)

        assert game.get_hand(p1).contains(draw_one)
        assert game.get_hand(p1).contains(draw_two)
        assert len(game.get_hand(p1).get_all()) == 2
