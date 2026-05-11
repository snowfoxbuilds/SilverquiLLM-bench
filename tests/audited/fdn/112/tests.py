"""Audited tests for Spinner of Souls (FDN collector number 112) — death trigger tokens."""
from __future__ import annotations
import pytest
from card_impl import SpinnerOfSouls
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
class TestSpinnerOfSoulsProperties:
    def test_is_creature(self):
        assert isinstance(SpinnerOfSouls(), Creature)
    def test_power_toughness(self):
        c = SpinnerOfSouls()
        assert c.base_power == 4 and c.base_toughness == 3
    def test_has_reach(self):
        assert Keyword.REACH in SpinnerOfSouls().keywords

@pytest.mark.ability
class TestSpinnerOfSoulsDeath:
    def test_another_creature_dies_reveals_creature_to_hand(self):
        game = _make_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        _place_on_battlefield(game, spinner, p1)
        spinner.register_triggers(game)
        # Add a creature card to library
        lib_creature = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2)
        p1.zones[Zone.LIBRARY].add(lib_creature)
        # Fire death for another nontoken creature
        other = Creature(name="Victim", owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": other, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) >= hand_before + 1
