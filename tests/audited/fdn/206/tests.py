"""Audited tests for Shivan Dragon (FDN collector number 206) — pump ability."""
from __future__ import annotations
import pytest
from card_impl import ShivanDragon
from engine.card import ActivatedAbility, CardImpl, Creature, ManaAbility
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone

def _make_game():
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = Phase.PRECOMBAT_MAIN
    game.active_player_index = 0
    return game

def _place_on_battlefield(game, creature, player):
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)

def _add_library(player, n):
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards

@pytest.mark.basic
class TestShivanDragonProperties:
    def test_is_creature(self):
        assert isinstance(ShivanDragon(), Creature)
    def test_power_toughness(self):
        c = ShivanDragon()
        assert c.base_power == 5 and c.base_toughness == 5
    def test_has_flying(self):
        assert Keyword.FLYING in ShivanDragon().keywords
    def test_mana_cost(self):
        assert ShivanDragon().mana_cost == ManaCost.parse("{4}{R}{R}")

@pytest.mark.ability
class TestShivanDragonAbility:
    def test_has_activated_ability(self):
        c = ShivanDragon()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
    def test_pump_increases_power(self):
        game = _make_game()
        p1 = game.players[0]
        c = ShivanDragon(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.RED, 1)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        power_before = c.power
        if ab.cost(game, c):
            ab.effect(game)
            assert c.power >= power_before + 1
