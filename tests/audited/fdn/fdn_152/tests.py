"""Audited tests for FDN 152 — Brineborn Cutthroat."""

from __future__ import annotations

from card_impl import BrinebornCutthroat
from engine.card import Creature
from engine.triggers import EventType
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestBrinebornCutthroatBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = BrinebornCutthroat(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BrinebornCutthroat(owner=None)
        assert card.name == "Brineborn Cutthroat"

    def test_mana_cost(self) -> None:
        card = BrinebornCutthroat(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}")

    def test_power_toughness(self) -> None:
        card = BrinebornCutthroat(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_has_flash(self) -> None:
        card = BrinebornCutthroat(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_subtypes(self) -> None:
        card = BrinebornCutthroat(owner=None)
        assert "Merfolk" in card.subtypes
        assert "Pirate" in card.subtypes


class TestBrinebornCutthroatTrigger:
    """Whenever you cast a spell during an opponent's turn, +1/+1 counter."""

    def test_counter_on_spell_during_opponent_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = BrinebornCutthroat(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        # Set active player to opponent (p2's turn)
        game.active_player_index = 1
        initial = getattr(card, "plus_one_counters", 0)
        game.trigger_manager.fire_event(
            game, EventType.SPELL_CAST, {"player": p1, "controller": p1}
        )
        _resolve_stack(game)
        assert getattr(card, "plus_one_counters", 0) == initial + 1

    def test_no_counter_on_own_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BrinebornCutthroat(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        # Active player is p1 (own turn)
        game.active_player_index = 0
        initial = getattr(card, "plus_one_counters", 0)
        game.trigger_manager.fire_event(
            game, EventType.SPELL_CAST, {"player": p1, "controller": p1}
        )
        _resolve_stack(game)
        assert getattr(card, "plus_one_counters", 0) == initial

    def test_no_counter_on_opponent_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = BrinebornCutthroat(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.active_player_index = 1
        initial = getattr(card, "plus_one_counters", 0)
        # Opponent casts, not us
        game.trigger_manager.fire_event(
            game, EventType.SPELL_CAST, {"player": p2, "controller": p2}
        )
        _resolve_stack(game)
        assert getattr(card, "plus_one_counters", 0) == initial
