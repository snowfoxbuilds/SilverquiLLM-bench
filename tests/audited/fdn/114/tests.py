"""Audited tests for Treetop Snarespinner (FDN collector number 114) — pump counter."""
from __future__ import annotations
import pytest
from card_impl import TreetopSnarespinner
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
class TestTreetopSnarespinnerProperties:
    def test_is_creature(self):
        assert isinstance(TreetopSnarespinner(), Creature)
    def test_power_toughness(self):
        c = TreetopSnarespinner()
        assert c.base_power == 1 and c.base_toughness == 4
    def test_has_reach(self):
        assert Keyword.REACH in TreetopSnarespinner().keywords
    def test_has_deathtouch(self):
        assert Keyword.DEATHTOUCH in TreetopSnarespinner().keywords

@pytest.mark.ability
class TestTreetopSnarespinnerAbility:
    def test_has_activated_ability(self):
        c = TreetopSnarespinner()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_cost_pays_2g_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = TreetopSnarespinner(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True

    def test_cost_fails_without_green(self):
        game = _make_game()
        p1 = game.players[0]
        c = TreetopSnarespinner(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.COLORLESS, 3)  # no green
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_effect_adds_counter_to_target(self):
        game = _make_game()
        p1 = game.players[0]
        c = TreetopSnarespinner(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        target = Creature(name="Target", owner=p1, controller=p1, base_power=2, base_toughness=2)
        _place_on_battlefield(game, target, p1)
        c._current_target = target
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        counters_before = getattr(target, "plus_one_counters", 0)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        assert getattr(target, "plus_one_counters", 0) == counters_before + 1
