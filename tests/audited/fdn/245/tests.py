"""Audited tests for Ruby, Daring Tracker (FDN collector number 245) — mana ability."""
from __future__ import annotations
import pytest
from card_impl import RubyDaringTracker
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
class TestRubyDaringTrackerProperties:
    def test_is_creature(self):
        assert isinstance(RubyDaringTracker(), Creature)
    def test_power_toughness(self):
        c = RubyDaringTracker()
        assert c.base_power == 1 and c.base_toughness == 2
    def test_has_haste(self):
        assert Keyword.HASTE in RubyDaringTracker().keywords

@pytest.mark.ability
class TestRubyDaringTrackerMana:
    def test_has_mana_ability(self):
        c = RubyDaringTracker()
        abilities = c.get_mana_abilities()
        assert len(abilities) >= 1

    def test_mana_ability_produces_red(self):
        game = _make_game()
        p1 = game.players[0]
        c = RubyDaringTracker(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = False
        abilities = c.get_mana_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.mana_produced(game)
        assert p1.mana_pool.get(ManaType.RED) >= 1

    def test_mana_ability_produces_green(self):
        game = _make_game()
        p1 = game.players[0]
        c = RubyDaringTracker(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = False
        abilities = c.get_mana_abilities()
        ab = abilities[1]
        ab.cost(game, c)
        ab.mana_produced(game)
        assert p1.mana_pool.get(ManaType.GREEN) >= 1

    def test_tap_cost_taps_creature(self):
        game = _make_game()
        p1 = game.players[0]
        c = RubyDaringTracker(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = False
        abilities = c.get_mana_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        assert c.is_tapped
