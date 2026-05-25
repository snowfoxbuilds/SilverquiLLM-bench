"""Audited tests for FDN 165 — Think Twice."""

from __future__ import annotations

from card_impl import ThinkTwice
from engine.card import CardImpl, Instant
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestThinkTwiceBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = ThinkTwice(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = ThinkTwice(owner=None)
        assert card.name == "Think Twice"

    def test_mana_cost(self) -> None:
        card = ThinkTwice(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}")

    def test_has_flashback_cost(self) -> None:
        card = ThinkTwice(owner=None)
        assert hasattr(card, "flashback_cost")
        assert card.flashback_cost == ManaCost.parse("{2}{U}")


class TestThinkTwiceResolve:
    """Draw a card."""

    def test_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ThinkTwice(owner=p1, controller=p1)
        # Put a card in library to draw
        lib_card = CardImpl(name="Mountain", owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before + 1

    def test_drawn_card_is_from_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ThinkTwice(owner=p1, controller=p1)
        lib_card = CardImpl(name="Unique Card", owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        spell.on_resolve(game)
        hand_names = [getattr(c, "name", "") for c in p1.zones[Zone.HAND].get_all()]
        assert "Unique Card" in hand_names
