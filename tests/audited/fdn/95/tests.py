"""Audited tests for Sower of Chaos (FDN collector number 95) — menace ability."""
from __future__ import annotations
import pytest
from card_impl import SowerOfChaos
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
class TestSowerOfChaosProperties:
    def test_is_creature(self):
        assert isinstance(SowerOfChaos(), Creature)
    def test_power_toughness(self):
        c = SowerOfChaos()
        assert c.base_power == 4 and c.base_toughness == 3
    def test_mana_cost(self):
        assert SowerOfChaos().mana_cost == ManaCost.parse("{3}{R}")

@pytest.mark.ability
class TestSowerOfChaosAbility:
    def test_has_activated_ability(self):
        c = SowerOfChaos()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_cost_pays_2r_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = SowerOfChaos(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.RED, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True

    def test_cost_fails_without_red(self):
        game = _make_game()
        p1 = game.players[0]
        c = SowerOfChaos(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.COLORLESS, 3)  # no red
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_effect_marks_target_cant_block(self):
        game = _make_game()
        p1, p2 = game.players
        c = SowerOfChaos(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        target = Creature(name="Blocker", owner=p2, controller=p2, base_power=2, base_toughness=2)
        _place_on_battlefield(game, target, p2)
        c._current_target = target
        p1.mana_pool.add(ManaType.RED, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        assert getattr(target, "_cant_block", False) is True
