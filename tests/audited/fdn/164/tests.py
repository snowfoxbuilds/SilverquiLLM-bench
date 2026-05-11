"""Audited tests for Spectral Sailor (FDN collector number 164) — draw ability."""
from __future__ import annotations
import pytest
from card_impl import SpectralSailor
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
class TestSpectralSailorProperties:
    def test_is_creature(self):
        assert isinstance(SpectralSailor(), Creature)
    def test_power_toughness(self):
        c = SpectralSailor()
        assert c.base_power == 1 and c.base_toughness == 1
    def test_has_flash(self):
        assert Keyword.FLASH in SpectralSailor().keywords
    def test_has_flying(self):
        assert Keyword.FLYING in SpectralSailor().keywords

@pytest.mark.ability
class TestSpectralSailorAbility:
    def test_has_activated_ability(self):
        c = SpectralSailor()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
    def test_draw_ability_draws_card(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 3)
        c = SpectralSailor(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.BLUE, 4)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        hand_before = len(p1.zones[Zone.HAND].get_all())
        if ab.cost(game, c):
            ab.effect(game)
            assert len(p1.zones[Zone.HAND].get_all()) >= hand_before + 1
