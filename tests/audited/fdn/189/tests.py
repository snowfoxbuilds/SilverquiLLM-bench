"""Audited tests for Axgard Cavalry (FDN collector number 189) — tap grant haste."""
from __future__ import annotations
import pytest
from card_impl import AxgardCavalry
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
class TestAxgardCavalryProperties:
    def test_is_creature(self):
        assert isinstance(AxgardCavalry(), Creature)
    def test_power_toughness(self):
        c = AxgardCavalry()
        assert c.base_power == 2 and c.base_toughness == 2
    def test_mana_cost(self):
        assert AxgardCavalry().mana_cost == ManaCost.parse("{1}{R}")

@pytest.mark.ability
class TestAxgardCavalryAbility:
    def test_has_activated_ability(self):
        c = AxgardCavalry()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
    def test_tap_cost_taps_creature(self):
        game = _make_game()
        p1 = game.players[0]
        c = AxgardCavalry(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = False
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        assert c.is_tapped

    def test_effect_grants_haste_to_target(self):
        game = _make_game()
        p1 = game.players[0]
        c = AxgardCavalry(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.is_tapped = False
        target = Creature(name="Target", owner=p1, controller=p1, base_power=3, base_toughness=3)
        _place_on_battlefield(game, target, p1)
        c._current_target = target
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        assert Keyword.HASTE in target.keywords
