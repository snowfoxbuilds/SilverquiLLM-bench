"""Audited tests for FDN 210 — Thrill of Possibility."""

from __future__ import annotations

from card_impl import ThrillOfPossibility
from engine.card import CardImpl, Instant
from engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestThrillOfPossibilityBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = ThrillOfPossibility(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = ThrillOfPossibility(owner=None)
        assert card.name == "Thrill of Possibility"

    def test_mana_cost(self) -> None:
        card = ThrillOfPossibility(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}")


class TestThrillOfPossibilityResolve:
    """Draw two cards (discard cost assumed paid during casting)."""

    def test_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Put cards in library to draw
        c1 = CardImpl(name="Card1", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        c2 = CardImpl(name="Card2", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)
        hand_before = len(game.get_hand(p1).get_all())
        spell = ThrillOfPossibility(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before + 2
