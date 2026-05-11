"""Audited tests for Infernal Vessel (FDN collector number 63) — death trigger drain."""
from __future__ import annotations
import pytest
from card_impl import InfernalVessel
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
class TestInfernalVesselProperties:
    def test_is_creature(self):
        assert isinstance(InfernalVessel(), Creature)
    def test_power_toughness(self):
        c = InfernalVessel()
        assert c.base_power == 2 and c.base_toughness == 1

@pytest.mark.ability
class TestInfernalVesselDeath:
    def test_death_returns_to_battlefield_if_not_demon(self):
        game = _make_game()
        p1 = game.players[0]
        c = InfernalVessel(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        # Move to graveyard to simulate dying
        game.get_battlefield(p1).remove(c)
        p1.zones[Zone.GRAVEYARD].add(c)
        _simulate_death(game, c)
        # Should return to battlefield since it wasn't a Demon
        assert game.get_battlefield(p1).contains(c)
