"""Audited tests for Garna, Bloodfist of Keld (FDN collector number 658) — other creature dies trigger."""
from __future__ import annotations
import pytest
from card_impl import GarnaBloodfistOfKeld
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
class TestGarnaProperties:
    def test_is_creature(self):
        assert isinstance(GarnaBloodfistOfKeld(), Creature)
    def test_power_toughness(self):
        c = GarnaBloodfistOfKeld()
        assert c.base_power == 4 and c.base_toughness == 3

@pytest.mark.ability
class TestGarnaDeath:
    def test_another_creature_dying_triggers(self):
        game = _make_game()
        p1, p2 = game.players
        garna = GarnaBloodfistOfKeld(owner=p1, controller=p1)
        _place_on_battlefield(game, garna, p1)
        garna.register_triggers(game)
        other = Creature(name="Victim", owner=p1, controller=p1)
        opp_life = p2.life
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": other, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        # Garna deals damage when another creature dies
        assert p2.life < opp_life
