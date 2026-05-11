"""Audited tests for Nine-Lives Familiar (FDN collector number 66) — death trigger gain life."""
from __future__ import annotations
import pytest
from card_impl import NineLivesFamiliar
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

def _place_on_battlefield(game, creature, player):
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)

def _simulate_death(game, creature, controller=None):
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": creature, "controller": controller})
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)

@pytest.mark.basic
class TestNineLivesFamiliarProperties:
    def test_is_creature(self):
        assert isinstance(NineLivesFamiliar(), Creature)
    def test_power_toughness(self):
        c = NineLivesFamiliar()
        assert c.base_power == 1 and c.base_toughness == 1

@pytest.mark.ability
class TestNineLivesFamiliarDeath:
    def test_death_returns_to_battlefield_with_counters(self):
        game = _make_game()
        p1 = game.players[0]
        c = NineLivesFamiliar(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.revival_counters = 8
        # Move to graveyard
        game.get_battlefield(p1).remove(c)
        p1.zones[Zone.GRAVEYARD].add(c)
        _simulate_death(game, c)
        # Should return to battlefield with fewer counters
        assert game.get_battlefield(p1).contains(c)
        assert c.revival_counters == 7
