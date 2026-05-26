"""Audited tests for FDN 202 — Hidetsugu's Second Rite."""

from __future__ import annotations

from card_impl import HidetsugusSecondRite
from engine.card import Instant
from engine.types import ManaCost
from test_utils import create_game


class TestHidetsugusSecondRiteBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = HidetsugusSecondRite(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = HidetsugusSecondRite(owner=None)
        assert card.name == "Hidetsugu's Second Rite"

    def test_mana_cost(self) -> None:
        card = HidetsugusSecondRite(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}")


class TestHidetsugusSecondRiteResolve:
    """If target player has exactly 10 life, deals 10 damage."""

    def test_deals_10_damage_at_exactly_10_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p2.life = 10
        spell = HidetsugusSecondRite(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)
        assert p2.life == 0

    def test_does_not_deal_damage_at_11_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p2.life = 11
        spell = HidetsugusSecondRite(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)
        assert p2.life == 11

    def test_does_not_deal_damage_at_9_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p2.life = 9
        spell = HidetsugusSecondRite(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)
        assert p2.life == 9

    def test_fizzles_if_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = HidetsugusSecondRite(owner=p1, controller=p1)
        spell.chosen_targets = [None]
        spell.on_resolve(game)  # Should not raise
