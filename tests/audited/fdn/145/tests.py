"""Audited tests for Resolute Reinforcements (FDN collector number 145) — ETB token + flash."""
from __future__ import annotations
import pytest
from card_impl import ResoluteReinforcements
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
class TestResoluteReinforcementsProperties:
    def test_is_creature(self):
        assert isinstance(ResoluteReinforcements(), Creature)
    def test_power_toughness(self):
        c = ResoluteReinforcements()
        assert c.base_power == 1 and c.base_toughness == 1
    def test_has_flash(self):
        assert Keyword.FLASH in ResoluteReinforcements().keywords
    def test_mana_cost(self):
        assert ResoluteReinforcements().mana_cost == ManaCost.parse("{1}{W}")

@pytest.mark.ability
class TestResoluteReinforcementsETB:
    def test_etb_creates_soldier_token(self):
        game = _make_game()
        p1 = game.players[0]
        c = ResoluteReinforcements(owner=p1, controller=p1)
        _simulate_etb(game, c)
        tokens = [x for x in game.get_battlefield(p1).get_all() if x.name == "Soldier"]
        assert len(tokens) >= 1
