"""Audited tests for FDN 135 — Ajani's Pridemate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# The conftest name-mangling turns "Ajani's" → "AjaniS" which doesn't
# match the impl class "AjanisPridemate".  Direct-load the implementation.
_impl_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "cards" / "fdn" / "fdn_135" / "card_impl.py"
_spec = importlib.util.spec_from_file_location("_fdn135_impl", _impl_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
AjanisPridemate = _mod.AjanisPridemate
from engine.card import Creature
from engine.triggers import EventType
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestAjanisPridematBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = AjanisPridemate(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AjanisPridemate(owner=None)
        assert card.name == "Ajani's Pridemate"

    def test_mana_cost(self) -> None:
        card = AjanisPridemate(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = AjanisPridemate(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = AjanisPridemate(owner=None)
        assert "Cat" in card.subtypes
        assert "Soldier" in card.subtypes


class TestAjanisPridemateTrigger:
    """Whenever you gain life, put a +1/+1 counter on this creature."""

    def test_gains_counter_on_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AjanisPridemate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        initial = getattr(card, "plus_one_counters", 0)
        game.trigger_manager.fire_event(
            game, EventType.GAINS_LIFE, {"player": p1, "amount": 3}
        )
        _resolve_stack(game)
        assert getattr(card, "plus_one_counters", 0) == initial + 1

    def test_no_counter_on_opponent_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = AjanisPridemate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        initial = getattr(card, "plus_one_counters", 0)
        game.trigger_manager.fire_event(
            game, EventType.GAINS_LIFE, {"player": p2, "amount": 3}
        )
        _resolve_stack(game)
        assert getattr(card, "plus_one_counters", 0) == initial

    def test_multiple_life_gain_events_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AjanisPridemate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        initial = getattr(card, "plus_one_counters", 0)
        game.trigger_manager.fire_event(
            game, EventType.GAINS_LIFE, {"player": p1, "amount": 1}
        )
        _resolve_stack(game)
        game.trigger_manager.fire_event(
            game, EventType.GAINS_LIFE, {"player": p1, "amount": 2}
        )
        _resolve_stack(game)
        assert getattr(card, "plus_one_counters", 0) == initial + 2
