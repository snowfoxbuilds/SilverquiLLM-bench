"""Audited tests for Wary Thespian (FDN collector number 235) — death trigger surveil."""
from __future__ import annotations
import pytest
from card_impl import WaryThespian
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
class TestWaryThespianProperties:
    def test_is_creature(self):
        assert isinstance(WaryThespian(), Creature)
    def test_power_toughness(self):
        c = WaryThespian()
        assert c.base_power == 3 and c.base_toughness == 1

@pytest.mark.ability
class TestWaryThespianDeath:
    def test_death_surveil_moves_card_to_graveyard(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        c = WaryThespian(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        _simulate_death(game, c)
        # Surveil 1 should move exactly 1 card from library to graveyard
        assert len(p1.zones[Zone.LIBRARY].get_all()) == lib_before - 1
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == gy_before + 1

    def test_death_surveil_no_crash_with_empty_library(self):
        game = _make_game()
        p1 = game.players[0]
        # Empty library
        c = WaryThespian(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        _simulate_death(game, c)
        # Should not crash; graveyard should not grow from surveil
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == gy_before
