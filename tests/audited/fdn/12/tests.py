"""Audited tests for Felidar Savior (FDN collector number 12) — ETB +1/+1 counters."""
from __future__ import annotations
import pytest
from card_impl import FelidarSavior
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Phase, Zone

def _make_game():
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = Phase.PRECOMBAT_MAIN
    game.active_player_index = 0
    return game

def _add_library(player, n):
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards

def _simulate_etb(game, creature, controller=None):
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": creature, "controller": controller})
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)

def _place_on_battlefield(game, creature, player):
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)

@pytest.mark.basic
class TestFelidarSaviorProperties:
    def test_is_creature(self):
        assert isinstance(FelidarSavior(), Creature)
    def test_power_toughness(self):
        c = FelidarSavior()
        assert c.base_power == 2 and c.base_toughness == 3
    def test_has_lifelink(self):
        assert Keyword.LIFELINK in FelidarSavior().keywords
    def test_mana_cost(self):
        assert FelidarSavior().mana_cost == ManaCost.parse("{3}{W}")

@pytest.mark.ability
class TestFelidarSaviorETB:
    def test_etb_adds_counter_to_target(self):
        game = _make_game()
        p1 = game.players[0]
        target = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(target)
        c = FelidarSavior(owner=p1, controller=p1)
        c.chosen_targets = [target]
        _simulate_etb(game, c)
        counters = getattr(target, "counters", {})
        assert counters.get("+1/+1", 0) >= 1 or target.base_power >= 3
