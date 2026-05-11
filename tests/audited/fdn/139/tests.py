"""Audited tests for Cathar Commando (FDN collector number 139) — sacrifice destroy."""
from __future__ import annotations
import pytest
from card_impl import CatharCommando
from engine.card import ActivatedAbility, CardImpl, Creature, ManaAbility
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone

from engine.card import Artifact, Enchantment

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
class TestCatharCommandoProperties:
    def test_is_creature(self):
        assert isinstance(CatharCommando(), Creature)
    def test_power_toughness(self):
        c = CatharCommando()
        assert c.base_power == 3 and c.base_toughness == 1
    def test_has_flash(self):
        assert Keyword.FLASH in CatharCommando().keywords
    def test_mana_cost(self):
        assert CatharCommando().mana_cost == ManaCost.parse("{1}{W}")

@pytest.mark.ability
class TestCatharCommandoAbility:
    def test_has_activated_ability(self):
        c = CatharCommando()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_sacrifice_cost_removes_from_battlefield(self):
        game = _make_game()
        p1 = game.players[0]
        c = CatharCommando(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True
        # After sacrifice, creature should no longer be on battlefield
        bf = game.get_battlefield(p1).get_all()
        assert c not in bf

    def test_sacrifice_fails_without_mana(self):
        game = _make_game()
        p1 = game.players[0]
        c = CatharCommando(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        # No mana
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_effect_destroys_target_artifact(self):
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        c = CatharCommando(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        target = Artifact(name="Sol Ring", owner=p2, controller=p2)
        _place_on_battlefield(game, target, p2)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        # Set the target for the ability
        c._current_target = target
        ab.effect(game)
        bf_p2 = game.get_battlefield(p2).get_all()
        assert target not in bf_p2

    def test_effect_destroys_target_enchantment(self):
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        c = CatharCommando(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        target = Enchantment(name="Pacifism", owner=p2, controller=p2)
        _place_on_battlefield(game, target, p2)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        c._current_target = target
        ab.effect(game)
        bf_p2 = game.get_battlefield(p2).get_all()
        assert target not in bf_p2

    def test_effect_no_op_when_target_not_on_battlefield(self):
        """If the target left the battlefield before resolution, nothing happens."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        c = CatharCommando(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        target = Artifact(name="Sol Ring", owner=p2, controller=p2)
        # Target is NOT on the battlefield
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        c._current_target = target
        bf_before = list(game.get_battlefield(p2).get_all())
        ab.effect(game)
        bf_after = list(game.get_battlefield(p2).get_all())
        assert bf_before == bf_after
