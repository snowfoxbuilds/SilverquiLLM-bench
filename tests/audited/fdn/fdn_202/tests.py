"""Audited tests for FDN 202 — Hidetsugu's Second Rite."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from engine.card import Instant
from engine.types import ManaCost
from tests.test_utils import create_game

# The conftest name derivation produces "HidetsuguSSecondRite" but the impl
# uses "HidetsugusSecondRite".  Import the real class directly.
_impl_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "cards" / "fdn" / "fdn_202" / "card_impl.py"
_spec = importlib.util.spec_from_file_location("_fdn202_direct", _impl_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
HidetsugusSecondRite = _mod.HidetsugusSecondRite


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
