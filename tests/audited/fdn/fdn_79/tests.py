"""Audited tests for FDN 79 — Boltwave."""

from __future__ import annotations

from card_impl import Boltwave
from engine.card import Sorcery
from engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestBoltwaveBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = Boltwave(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = Boltwave(owner=None)
        assert card.name == "Boltwave"

    def test_mana_cost(self) -> None:
        card = Boltwave(owner=None)
        assert card.mana_cost == ManaCost.parse("{R}")


class TestBoltwaveResolve:
    """Deals 3 damage to each opponent."""

    def test_deals_3_damage_to_opponent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = Boltwave(owner=p1, controller=p1)
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 3

    def test_does_not_damage_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Boltwave(owner=p1, controller=p1)
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before

    def test_no_crash_without_controller(self) -> None:
        game = create_game()
        card = Boltwave(owner=None, controller=None)
        p2_life = game.players[1].life
        card.on_resolve(game)
        # With no controller, should do nothing
        assert game.players[1].life == p2_life
