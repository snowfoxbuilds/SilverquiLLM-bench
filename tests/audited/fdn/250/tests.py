"""Audited tests for Burnished Hart (FDN collector number 250) — sacrifice land search."""
from __future__ import annotations
import pytest
from card_impl import BurnishedHart
from engine.card import ActivatedAbility, CardImpl, Creature, ManaAbility
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone

from engine.card import ArtifactCreature

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
class TestBurnishedHartProperties:
    def test_is_artifact_creature(self):
        assert isinstance(BurnishedHart(), ArtifactCreature)
    def test_power_toughness(self):
        c = BurnishedHart()
        assert c.base_power == 2 and c.base_toughness == 2

@pytest.mark.ability
class TestBurnishedHartAbility:
    def test_has_activated_ability(self):
        c = BurnishedHart()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_sacrifice_cost_pays_3_and_removes(self):
        game = _make_game()
        p1 = game.players[0]
        c = BurnishedHart(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True
        bf = game.get_battlefield(p1).get_all()
        assert c not in bf

    def test_sacrifice_fails_without_enough_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = BurnishedHart(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)  # Only 2 of 3 needed
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_effect_puts_basic_lands_on_battlefield_tapped(self):
        game = _make_game()
        p1 = game.players[0]
        c = BurnishedHart(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        # Add basic lands to library
        land1 = CardImpl(name="Forest")
        land1.is_basic_land = True
        land1.owner = p1
        land2 = CardImpl(name="Plains")
        land2.is_basic_land = True
        land2.owner = p1
        p1.zones[Zone.LIBRARY].add(land1)
        p1.zones[Zone.LIBRARY].add(land2)
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        bf = game.get_battlefield(p1).get_all()
        lands_on_bf = [x for x in bf if getattr(x, "is_basic_land", False)]
        assert len(lands_on_bf) == 2
        assert all(x.is_tapped for x in lands_on_bf)
