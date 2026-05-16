"""Audited tests for FDN 229 — Nessian Hornbeetle."""
from __future__ import annotations
from card_impl import NessianHornbeetle
from engine.card import Creature
from engine.types import CardType, ManaCost
from tests.test_utils import create_game
from engine.events import BeginningOfCombatTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestNessianHornbeetleBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = NessianHornbeetle(owner=None)
        assert card.name == 'Nessian Hornbeetle'

    def test_mana_cost(self) -> None:
        card = NessianHornbeetle(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{G}')

    def test_power_toughness(self) -> None:
        card = NessianHornbeetle(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = NessianHornbeetle(owner=None)
        assert 'Insect' in card.subtypes

class TestNessianHornbeetleTrigger:
    """Beginning of combat: +1/+1 counter if you control power 4+ creature."""

    def test_gets_counter_with_power_4_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        beetle = NessianHornbeetle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(beetle)
        big = Creature(name='Big', base_power=4, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(big)
        beetle.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
        _resolve_stack(game)
        assert beetle.plus_one_counters >= 1

    def test_no_counter_without_power_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        beetle = NessianHornbeetle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(beetle)
        small = Creature(name='Small', base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(small)
        beetle.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
        _resolve_stack(game)
        assert getattr(beetle, 'plus_one_counters', 0) == 0

    def test_no_counter_on_opponent_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        game.active_player_index = 1
        beetle = NessianHornbeetle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(beetle)
        big = Creature(name='Big', base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(big)
        beetle.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
        _resolve_stack(game)
        assert getattr(beetle, 'plus_one_counters', 0) == 0
