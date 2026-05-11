"""Audited tests for Mild-Mannered Librarian (FDN collector number 228) — transform ability."""
from __future__ import annotations
import pytest
from card_impl import MildManneredLibrarian
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
class TestMildManneredLibrarianProperties:
    def test_is_creature(self):
        assert isinstance(MildManneredLibrarian(), Creature)
    def test_power_toughness(self):
        c = MildManneredLibrarian()
        assert c.base_power == 1 and c.base_toughness == 1
    def test_mana_cost(self):
        assert MildManneredLibrarian().mana_cost == ManaCost.parse("{G}")

@pytest.mark.ability
class TestMildManneredLibrarianAbility:
    def test_has_activated_ability(self):
        c = MildManneredLibrarian()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_transform_adds_counters_and_draws(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        c = MildManneredLibrarian(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        counters_before = getattr(c, "plus_one_counters", 0)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True
        ab.effect(game)
        assert getattr(c, "plus_one_counters", 0) == counters_before + 2
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_activate_only_once(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        c = MildManneredLibrarian(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.GREEN, 2)
        p1.mana_pool.add(ManaType.COLORLESS, 6)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        # Second activation should fail
        result2 = ab.cost(game, c)
        assert result2 is False

    def test_cost_fails_without_enough_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = MildManneredLibrarian(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        # Only 1G, need 3G
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False
