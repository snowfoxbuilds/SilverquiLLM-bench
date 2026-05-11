"""Audited tests for Inspiring Overseer (FDN collector number 496) — ETB life+draw."""
from __future__ import annotations
import pytest
from card_impl import InspiringOverseer
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

@pytest.mark.basic
class TestInspiringOverseerProperties:
    def test_is_creature(self):
        assert isinstance(InspiringOverseer(), Creature)
    def test_power_toughness(self):
        c = InspiringOverseer()
        assert c.base_power == 2 and c.base_toughness == 1
    def test_has_flying(self):
        assert Keyword.FLYING in InspiringOverseer().keywords
    def test_mana_cost(self):
        assert InspiringOverseer().mana_cost == ManaCost.parse("{2}{W}")
    def test_subtypes(self):
        c = InspiringOverseer()
        assert "Angel" in c.subtypes and "Cleric" in c.subtypes

@pytest.mark.ability
class TestInspiringOverseerETB:
    def test_etb_gains_life(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 3)
        c = InspiringOverseer(owner=p1, controller=p1)
        life_before = p1.life
        _simulate_etb(game, c)
        assert p1.life == life_before + 1
    def test_etb_draws_card(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 3)
        c = InspiringOverseer(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_etb(game, c)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1
