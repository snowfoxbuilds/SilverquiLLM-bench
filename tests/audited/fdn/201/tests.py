"""Audited tests for Heartfire Immolator (FDN collector number 201) — sacrifice damage."""
from __future__ import annotations
import pytest
from card_impl import HeartfireImmolator
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
class TestHeartfireImmolatorProperties:
    def test_is_creature(self):
        assert isinstance(HeartfireImmolator(), Creature)
    def test_power_toughness(self):
        c = HeartfireImmolator()
        assert c.base_power == 2 and c.base_toughness == 2
    def test_has_prowess(self):
        assert Keyword.PROWESS in HeartfireImmolator().keywords

@pytest.mark.ability
class TestHeartfireImmolatorAbility:
    def test_has_activated_ability(self):
        c = HeartfireImmolator()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_sacrifice_cost_pays_red_and_removes(self):
        game = _make_game()
        p1 = game.players[0]
        c = HeartfireImmolator(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.RED, 1)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True
        bf = game.get_battlefield(p1).get_all()
        assert c not in bf

    def test_sacrifice_fails_without_red_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = HeartfireImmolator(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        # No mana
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_deals_damage_equal_to_power(self):
        game = _make_game()
        p1, p2 = game.players
        c = HeartfireImmolator(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.RED, 1)
        target = Creature(name="Victim", owner=p2, controller=p2, base_power=1, base_toughness=5)
        _place_on_battlefield(game, target, p2)
        c._current_target = target
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        # HeartfireImmolator has base_power 2
        assert target.damage_marked >= 2
