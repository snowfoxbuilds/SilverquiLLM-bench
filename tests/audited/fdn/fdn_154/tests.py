"""Audited tests for FDN 154 — Extravagant Replication."""
from __future__ import annotations
from card_impl import ExtravagantReplication
from engine.card import Creature, Enchantment
from engine.types import CardType, ManaCost
from tests.test_utils import create_game
from engine.events import BeginningOfUpkeepTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestExtravagantReplicationBasics:
    """Basic card properties."""

    def test_is_enchantment(self) -> None:
        card = ExtravagantReplication(owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        card = ExtravagantReplication(owner=None)
        assert card.name == 'Extravagant Replication'

    def test_mana_cost(self) -> None:
        card = ExtravagantReplication(owner=None)
        assert card.mana_cost == ManaCost.parse('{4}{U}{U}')

class TestExtravagantReplicationTrigger:
    """At upkeep, create token copy of another nonland permanent you control."""

    def test_creates_token_copy_at_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ench = ExtravagantReplication(owner=p1, controller=p1)
        target = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(ench)
        game.get_battlefield(p1).add(target)
        ench.register_triggers(game)
        game.active_player_index = 0
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(target)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        bf = list(game.get_battlefield(p1).get_all())
        bear_count = sum((1 for c in bf if getattr(c, 'name', '') == 'Bear'))
        assert bear_count >= 2

    def test_does_not_trigger_on_opponent_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ench = ExtravagantReplication(owner=p1, controller=p1)
        target = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(ench)
        game.get_battlefield(p1).add(target)
        ench.register_triggers(game)
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        bf = list(game.get_battlefield(p1).get_all())
        bear_count = sum((1 for c in bf if getattr(c, 'name', '') == 'Bear'))
        assert bear_count == 1

    def test_no_candidates_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ench = ExtravagantReplication(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ench)
        ench.register_triggers(game)
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        bf = list(game.get_battlefield(p1).get_all())
        assert len(bf) == 1
