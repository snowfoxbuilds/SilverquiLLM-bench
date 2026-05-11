"""Audited tests for Arbiter of Woe (FDN collector number 55) — ETB discard+drain."""
from __future__ import annotations
import pytest
from card_impl import ArbiterOfWoe
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
class TestArbiterOfWoeProperties:
    def test_is_creature(self):
        assert isinstance(ArbiterOfWoe(), Creature)
    def test_power_toughness(self):
        c = ArbiterOfWoe()
        assert c.base_power == 5 and c.base_toughness == 4
    def test_has_flying(self):
        assert Keyword.FLYING in ArbiterOfWoe().keywords
    def test_mana_cost(self):
        assert ArbiterOfWoe().mana_cost == ManaCost.parse("{4}{B}{B}")

@pytest.mark.ability
class TestArbiterOfWoeETB:
    def test_etb_opponent_loses_2_life(self):
        game = _make_game()
        p1, p2 = game.players
        _add_library(p1, 3)
        hand_card = CardImpl(name="DiscardMe")
        hand_card.owner = p2
        p2.zones[Zone.HAND].add(hand_card)
        c = ArbiterOfWoe(owner=p1, controller=p1)
        opp_life = p2.life
        _simulate_etb(game, c)
        assert p2.life == opp_life - 2
    def test_etb_controller_gains_2_life(self):
        game = _make_game()
        p1, p2 = game.players
        _add_library(p1, 3)
        hand_card = CardImpl(name="DiscardMe")
        hand_card.owner = p2
        p2.zones[Zone.HAND].add(hand_card)
        c = ArbiterOfWoe(owner=p1, controller=p1)
        my_life = p1.life
        _simulate_etb(game, c)
        assert p1.life == my_life + 2
