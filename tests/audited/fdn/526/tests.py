"""Audited tests for Skeleton Archer (FDN collector number 526) — ETB 1 damage."""
from __future__ import annotations
import pytest
from card_impl import SkeletonArcher
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

@pytest.mark.basic
class TestSkeletonArcherProperties:
    def test_is_creature(self):
        assert isinstance(SkeletonArcher(), Creature)
    def test_power_toughness(self):
        c = SkeletonArcher()
        assert c.base_power == 3 and c.base_toughness == 3
    def test_mana_cost(self):
        assert SkeletonArcher().mana_cost == ManaCost.parse("{3}{B}")

@pytest.mark.ability
class TestSkeletonArcherETB:
    def test_etb_deals_1_damage_to_player(self):
        game = _make_game()
        p1, p2 = game.players
        c = SkeletonArcher(owner=p1, controller=p1)
        c.chosen_targets = [p2]
        life_before = p2.life
        _simulate_etb(game, c)
        assert p2.life == life_before - 1
