"""Audited tests for Massacre Wurm (FDN collector number 714) — ETB -2/-2 to opponents."""
from __future__ import annotations
import pytest
from card_impl import MassacreWurm
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
class TestMassacreWurmProperties:
    def test_is_creature(self):
        assert isinstance(MassacreWurm(), Creature)
    def test_power_toughness(self):
        c = MassacreWurm()
        assert c.base_power == 6 and c.base_toughness == 5
    def test_mana_cost(self):
        assert MassacreWurm().mana_cost == ManaCost.parse("{3}{B}{B}{B}")

@pytest.mark.ability
class TestMassacreWurmETB:
    def test_etb_registers_debuff_effect(self):
        game = _make_game()
        p1, p2 = game.players
        target = Creature(name="Bear", owner=p2, controller=p2, base_power=3, base_toughness=3)
        game.get_battlefield(p2).add(target)
        c = MassacreWurm(owner=p1, controller=p1)
        effects_before = len(game.effect_manager._effects)
        _simulate_etb(game, c)
        assert len(game.effect_manager._effects) > effects_before

    def test_etb_debuffs_applied(self):
        game = _make_game()
        p1, p2 = game.players
        target = Creature(name="Bear", owner=p2, controller=p2, base_power=3, base_toughness=3)
        game.get_battlefield(p2).add(target)
        c = MassacreWurm(owner=p1, controller=p1)
        _simulate_etb(game, c)
        game.effect_manager.apply_all(game)
        assert target.base_power <= 1
