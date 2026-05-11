"""Audited tests for Elvish Archdruid (FDN collector number 219) — mana+lord."""
from __future__ import annotations
import pytest
from card_impl import ElvishArchdruid
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
class TestElvishArchdruidProperties:
    def test_is_creature(self):
        assert isinstance(ElvishArchdruid(), Creature)
    def test_power_toughness(self):
        c = ElvishArchdruid()
        assert c.base_power == 2 and c.base_toughness == 2
    def test_mana_cost(self):
        assert ElvishArchdruid().mana_cost == ManaCost.parse("{1}{G}{G}")
    def test_subtypes(self):
        c = ElvishArchdruid()
        assert "Elf" in c.subtypes

@pytest.mark.ability
class TestElvishArchdruidMana:
    def test_has_mana_ability(self):
        c = ElvishArchdruid()
        abilities = c.get_mana_abilities()
        assert len(abilities) >= 1
    def test_mana_ability_produces_green_per_elf(self):
        game = _make_game()
        p1 = game.players[0]
        archdruid = ElvishArchdruid(owner=p1, controller=p1)
        _place_on_battlefield(game, archdruid, p1)
        archdruid.is_tapped = False
        # Add another elf
        elf2 = Creature(name="Elf", owner=p1, controller=p1, subtypes={"Elf"}, base_power=1, base_toughness=1)
        game.get_battlefield(p1).add(elf2)
        abilities = archdruid.get_mana_abilities()
        ab = abilities[0]
        ab.cost(game, archdruid)
        ab.mana_produced(game)
        # Should produce G for each elf controlled (at least 2 — archdruid + elf2)
        assert p1.mana_pool.get(ManaType.GREEN) >= 2
