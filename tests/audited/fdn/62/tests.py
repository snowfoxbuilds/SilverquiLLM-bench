"""Audited tests for Hungry Ghoul (FDN collector number 62) — sacrifice +1/+1."""
from __future__ import annotations
import pytest
from card_impl import HungryGhoul
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
class TestHungryGhoulProperties:
    def test_is_creature(self):
        assert isinstance(HungryGhoul(), Creature)
    def test_power_toughness(self):
        c = HungryGhoul()
        assert c.base_power == 2 and c.base_toughness == 2
    def test_mana_cost(self):
        assert HungryGhoul().mana_cost == ManaCost.parse("{1}{B}")

@pytest.mark.ability
class TestHungryGhoulAbility:
    def test_has_activated_ability(self):
        c = HungryGhoul()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_sacrifice_another_adds_counter(self):
        game = _make_game()
        p1 = game.players[0]
        c = HungryGhoul(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        victim = Creature(name="Victim", owner=p1, controller=p1, base_power=1, base_toughness=1)
        _place_on_battlefield(game, victim, p1)
        c._sacrifice_target = victim
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        counters_before = getattr(c, "plus_one_counters", 0)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True
        ab.effect(game)
        assert getattr(c, "plus_one_counters", 0) == counters_before + 1

    def test_cannot_sacrifice_self(self):
        game = _make_game()
        p1 = game.players[0]
        c = HungryGhoul(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c._sacrifice_target = c  # trying to sacrifice self
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_fails_without_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = HungryGhoul(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        victim = Creature(name="Victim", owner=p1, controller=p1, base_power=1, base_toughness=1)
        _place_on_battlefield(game, victim, p1)
        c._sacrifice_target = victim
        # No mana
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False
