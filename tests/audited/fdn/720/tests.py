"""Audited tests for Pelakka Wurm (FDN collector number 720) — ETB gain 7 life."""
from __future__ import annotations
import pytest
from card_impl import PelakkaWurm
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

def _simulate_death(game, creature, controller=None):
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": creature, "controller": controller})
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)

@pytest.mark.basic
class TestPelakkaWurmProperties:
    def test_is_creature(self):
        assert isinstance(PelakkaWurm(), Creature)
    def test_power_toughness(self):
        c = PelakkaWurm()
        assert c.base_power == 7 and c.base_toughness == 7
    def test_has_trample(self):
        assert Keyword.TRAMPLE in PelakkaWurm().keywords
    def test_mana_cost(self):
        assert PelakkaWurm().mana_cost == ManaCost.parse("{4}{G}{G}{G}")

@pytest.mark.ability
class TestPelakkaWurmETB:
    def test_etb_gains_7_life(self):
        game = _make_game()
        p1 = game.players[0]
        c = PelakkaWurm(owner=p1, controller=p1)
        life_before = p1.life
        _simulate_etb(game, c)
        assert p1.life == life_before + 7

@pytest.mark.ability
class TestPelakkaWurmDeath:
    def test_dies_draws_card(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 3)
        c = PelakkaWurm(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_death(game, c)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1
