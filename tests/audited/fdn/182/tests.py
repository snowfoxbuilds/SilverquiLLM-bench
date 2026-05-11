"""Audited tests for Reassembling Skeleton (FDN collector number 182) — graveyard recursion."""
from __future__ import annotations
import pytest
from card_impl import ReassemblingSkeleton
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
class TestReassemblingSkeletonProperties:
    def test_is_creature(self):
        assert isinstance(ReassemblingSkeleton(), Creature)
    def test_power_toughness(self):
        c = ReassemblingSkeleton()
        assert c.base_power == 1 and c.base_toughness == 1
    def test_mana_cost(self):
        assert ReassemblingSkeleton().mana_cost == ManaCost.parse("{1}{B}")

@pytest.mark.ability
class TestReassemblingSkeletonAbility:
    def test_has_activated_ability(self):
        c = ReassemblingSkeleton()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_returns_from_graveyard_to_battlefield_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        c = ReassemblingSkeleton(owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(c)
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True
        ab.effect(game)
        bf = game.get_battlefield(p1).get_all()
        assert c in bf
        assert c.is_tapped

    def test_cost_fails_when_not_in_graveyard(self):
        game = _make_game()
        p1 = game.players[0]
        c = ReassemblingSkeleton(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_cost_fails_without_black_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = ReassemblingSkeleton(owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(c)
        p1.mana_pool.add(ManaType.COLORLESS, 2)  # no black
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False
