"""Audited tests for Meteor Golem (FDN collector number 256) — ETB destroy nonland."""
from __future__ import annotations
import pytest
from card_impl import MeteorGolem
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
class TestMeteorGolemProperties:
    def test_is_artifact_creature(self):
        assert isinstance(MeteorGolem(), ArtifactCreature)
    def test_power_toughness(self):
        c = MeteorGolem()
        assert c.base_power == 3 and c.base_toughness == 3
    def test_mana_cost(self):
        assert MeteorGolem().mana_cost == ManaCost.parse("{7}")

@pytest.mark.ability
class TestMeteorGolemETB:
    def test_etb_destroys_target(self):
        game = _make_game()
        p1, p2 = game.players
        target = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_battlefield(p2).add(target)
        c = MeteorGolem(owner=p1, controller=p1)
        c.chosen_targets = [target]
        _simulate_etb(game, c)
        assert not game.get_battlefield(p2).contains(target)
