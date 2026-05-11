"""Audited tests for Cloudblazer (FDN collector number 653) — ETB life+draw."""
from __future__ import annotations
import pytest
from card_impl import Cloudblazer
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
class TestCloudBlazerProperties:
    def test_is_creature(self):
        assert isinstance(Cloudblazer(), Creature)
    def test_power_toughness(self):
        c = Cloudblazer()
        assert c.base_power == 2 and c.base_toughness == 2
    def test_has_flying(self):
        assert Keyword.FLYING in Cloudblazer().keywords
    def test_mana_cost(self):
        assert Cloudblazer().mana_cost == ManaCost.parse("{3}{W}{U}")

@pytest.mark.ability
class TestCloudBlazerETB:
    def test_etb_gains_2_life(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        c = Cloudblazer(owner=p1, controller=p1)
        life_before = p1.life
        _simulate_etb(game, c)
        assert p1.life == life_before + 2
    def test_etb_draws_2_cards(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        c = Cloudblazer(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_etb(game, c)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 2
