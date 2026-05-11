"""Audited tests for Fiendish Panda (FDN collector number 120) — death trigger draw."""
from __future__ import annotations
import pytest
from card_impl import FiendishPanda
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
class TestFiendishPandaProperties:
    def test_is_creature(self):
        assert isinstance(FiendishPanda(), Creature)
    def test_power_toughness(self):
        c = FiendishPanda()
        assert c.base_power == 3 and c.base_toughness == 2

@pytest.mark.ability
class TestFiendishPandaDeath:
    def test_death_returns_creature_from_graveyard(self):
        game = _make_game()
        p1 = game.players[0]
        # Put a small non-Bear creature in graveyard
        target = Creature(name="Knight", owner=p1, controller=p1, subtypes={"Knight"},
                         mana_cost=ManaCost.parse("{1}{W}"), base_power=2, base_toughness=2)
        p1.zones[Zone.GRAVEYARD].add(target)
        c = FiendishPanda(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        _simulate_death(game, c)
        # The creature should be returned from graveyard to battlefield
        assert game.get_battlefield(p1).contains(target)
