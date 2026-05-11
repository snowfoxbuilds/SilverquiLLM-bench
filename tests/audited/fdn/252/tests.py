"""Audited tests for Gleaming Barrier (FDN collector number 252) — death trigger Treasure."""
from __future__ import annotations
import pytest
from card_impl import GleamingBarrier
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Phase, Zone

from engine.card import ArtifactCreature

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
class TestGleamingBarrierProperties:
    def test_is_artifact_creature(self):
        assert isinstance(GleamingBarrier(), ArtifactCreature)
    def test_power_toughness(self):
        c = GleamingBarrier()
        assert c.base_power == 0 and c.base_toughness == 4
    def test_has_defender(self):
        assert Keyword.DEFENDER in GleamingBarrier().keywords

@pytest.mark.ability
class TestGleamingBarrierDeath:
    def test_death_creates_treasure(self):
        game = _make_game()
        p1 = game.players[0]
        c = GleamingBarrier(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        _simulate_death(game, c)
        bf = game.get_battlefield(p1).get_all()
        tokens = [x for x in bf if x.name == "Treasure"]
        assert len(tokens) >= 1
