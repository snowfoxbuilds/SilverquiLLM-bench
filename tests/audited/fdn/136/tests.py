"""Audited tests for Angel of Finality (FDN collector number 136) — ETB exile graveyard."""
from __future__ import annotations
import pytest
from card_impl import AngelOfFinality
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
class TestAngelOfFinalityProperties:
    def test_is_creature(self):
        assert isinstance(AngelOfFinality(), Creature)
    def test_power_toughness(self):
        c = AngelOfFinality()
        assert c.base_power == 3 and c.base_toughness == 4
    def test_has_flying(self):
        assert Keyword.FLYING in AngelOfFinality().keywords
    def test_mana_cost(self):
        assert AngelOfFinality().mana_cost == ManaCost.parse("{3}{W}")

@pytest.mark.ability
class TestAngelOfFinalityETB:
    def test_etb_exiles_target_graveyard(self):
        game = _make_game()
        p1, p2 = game.players
        gy_card = CardImpl(name="Dead Card")
        gy_card.owner = p2
        p2.zones[Zone.GRAVEYARD].add(gy_card)
        c = AngelOfFinality(owner=p1, controller=p1)
        c.chosen_targets = [p2]
        _simulate_etb(game, c)
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 0
