"""Audited tests for Infestation Sage (FDN collector number 64) — death trigger token."""
from __future__ import annotations
import pytest
from card_impl import InfestationSage
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
class TestInfestationSageProperties:
    def test_is_creature(self):
        assert isinstance(InfestationSage(), Creature)
    def test_power_toughness(self):
        c = InfestationSage()
        assert c.base_power == 1 and c.base_toughness == 1
    def test_mana_cost(self):
        assert InfestationSage().mana_cost == ManaCost.parse("{B}")

@pytest.mark.ability
class TestInfestationSageDeath:
    def test_death_creates_insect_token(self):
        game = _make_game()
        p1 = game.players[0]
        c = InfestationSage(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        _simulate_death(game, c)
        bf = game.get_battlefield(p1).get_all()
        tokens = [x for x in bf if "Insect" in getattr(x, "subtypes", set())]
        assert len(tokens) >= 1

@pytest.mark.edge
class TestInfestationSageEdge:
    def test_no_trigger_for_other_creature_dying(self):
        game = _make_game()
        p1 = game.players[0]
        sage = InfestationSage(owner=p1, controller=p1)
        sage.register_triggers(game)
        other = Creature(name="Other", owner=p1, controller=p1)
        bf_before = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": other, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert len(game.get_battlefield(p1).get_all()) == bf_before
