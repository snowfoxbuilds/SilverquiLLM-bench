"""Audited tests for Vampire Soulcaller (FDN collector number 75) — ETB graveyard recursion."""
from __future__ import annotations
import pytest
from card_impl import VampireSoulcaller
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
class TestVampireSoulcallerProperties:
    def test_is_creature(self):
        assert isinstance(VampireSoulcaller(), Creature)
    def test_power_toughness(self):
        c = VampireSoulcaller()
        assert c.base_power == 3 and c.base_toughness == 2
    def test_has_flying(self):
        assert Keyword.FLYING in VampireSoulcaller().keywords
    def test_mana_cost(self):
        assert VampireSoulcaller().mana_cost == ManaCost.parse("{4}{B}")

@pytest.mark.ability
class TestVampireSoulcallerETB:
    def test_etb_returns_creature_from_graveyard_to_hand(self):
        game = _make_game()
        p1 = game.players[0]
        gy_creature = Creature(name="Dead Bear", owner=p1, base_power=2, base_toughness=2)
        p1.zones[Zone.GRAVEYARD].add(gy_creature)
        c = VampireSoulcaller(owner=p1, controller=p1)
        c.chosen_targets = [gy_creature]
        _simulate_etb(game, c)
        assert p1.zones[Zone.HAND].contains(gy_creature)
        assert not p1.zones[Zone.GRAVEYARD].contains(gy_creature)
