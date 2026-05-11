"""Audited tests for Rune-Sealed Wall (FDN collector number 49) — tap surveil."""
from __future__ import annotations
import pytest
from card_impl import RuneSealedWall
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
class TestRuneSealedWallProperties:
    def test_is_artifact_creature(self):
        assert isinstance(RuneSealedWall(), ArtifactCreature)
    def test_power_toughness(self):
        c = RuneSealedWall()
        assert c.base_power == 0 and c.base_toughness == 6
    def test_has_defender(self):
        assert Keyword.DEFENDER in RuneSealedWall().keywords

@pytest.mark.ability
class TestRuneSealedWallAbility:
    def test_has_activated_ability(self):
        c = RuneSealedWall()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
    def test_tap_ability_taps_creature(self):
        game = _make_game()
        p1 = game.players[0]
        c = RuneSealedWall(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        _add_library(p1, 3)
        c.is_tapped = False
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        assert c.is_tapped

    def test_surveil_moves_card_from_library_to_graveyard(self):
        game = _make_game()
        p1 = game.players[0]
        c = RuneSealedWall(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        _add_library(p1, 3)
        c.is_tapped = False
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())
        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        assert len(p1.zones[Zone.LIBRARY].get_all()) == lib_before - 1
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == gy_before + 1
