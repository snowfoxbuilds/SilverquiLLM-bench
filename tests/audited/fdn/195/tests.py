"""Audited tests for Fanatical Firebrand (FDN collector number 195) — sacrifice damage."""
from __future__ import annotations
import pytest
from card_impl import FanaticalFirebrand
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
class TestFanaticalFirebrandProperties:
    def test_is_creature(self):
        assert isinstance(FanaticalFirebrand(), Creature)
    def test_power_toughness(self):
        c = FanaticalFirebrand()
        assert c.base_power == 1 and c.base_toughness == 1
    def test_has_haste(self):
        assert Keyword.HASTE in FanaticalFirebrand().keywords
    def test_mana_cost(self):
        assert FanaticalFirebrand().mana_cost == ManaCost.parse("{R}")

@pytest.mark.ability
class TestFanaticalFirebrandAbility:
    def test_has_activated_ability(self):
        c = FanaticalFirebrand()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_sacrifice_cost_taps_and_removes(self):
        game = _make_game()
        p1 = game.players[0]
        c = FanaticalFirebrand(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = False
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True
        assert c.is_tapped
        bf = game.get_battlefield(p1).get_all()
        assert c not in bf

    def test_sacrifice_fails_when_already_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        c = FanaticalFirebrand(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = True
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_deals_1_damage_to_target(self):
        game = _make_game()
        p1, p2 = game.players
        c = FanaticalFirebrand(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = False
        target = Creature(name="Target", owner=p2, controller=p2, base_power=2, base_toughness=3)
        _place_on_battlefield(game, target, p2)
        c._current_target = target
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        assert target.damage_marked >= 1
