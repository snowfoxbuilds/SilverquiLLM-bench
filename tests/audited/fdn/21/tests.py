"""Audited tests for Prideful Parent (FDN collector number 21) — ETB token."""
from __future__ import annotations
import pytest
from card_impl import PridefulParent
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
class TestPridefulParentProperties:
    def test_is_creature(self):
        assert isinstance(PridefulParent(), Creature)
    def test_power_toughness(self):
        c = PridefulParent()
        assert c.base_power == 2 and c.base_toughness == 2
    def test_has_vigilance(self):
        assert Keyword.VIGILANCE in PridefulParent().keywords
    def test_mana_cost(self):
        assert PridefulParent().mana_cost == ManaCost.parse("{2}{W}")

@pytest.mark.ability
class TestPridefulParentETB:
    def test_etb_creates_cat_token(self):
        game = _make_game()
        p1 = game.players[0]
        c = PridefulParent(owner=p1, controller=p1)
        bf_before = len(game.get_battlefield(p1).get_all())
        _simulate_etb(game, c)
        bf = game.get_battlefield(p1).get_all()
        tokens = [x for x in bf if x.name == "Cat"]
        assert len(tokens) >= 1
    def test_cat_token_is_1_1(self):
        game = _make_game()
        p1 = game.players[0]
        c = PridefulParent(owner=p1, controller=p1)
        _simulate_etb(game, c)
        tokens = [x for x in game.get_battlefield(p1).get_all() if x.name == "Cat"]
        assert tokens[0].base_power == 1 and tokens[0].base_toughness == 1
