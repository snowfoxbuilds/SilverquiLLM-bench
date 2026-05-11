"""Audited tests for Krenko, Mob Boss (FDN collector number 204) — tap create tokens."""
from __future__ import annotations
import pytest
from card_impl import KrenkoMobBoss
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
class TestKrenkoMobBossProperties:
    def test_is_creature(self):
        assert isinstance(KrenkoMobBoss(), Creature)
    def test_power_toughness(self):
        c = KrenkoMobBoss()
        assert c.base_power == 3 and c.base_toughness == 3
    def test_mana_cost(self):
        assert KrenkoMobBoss().mana_cost == ManaCost.parse("{2}{R}{R}")

@pytest.mark.ability
class TestKrenkoMobBossAbility:
    def test_has_activated_ability(self):
        c = KrenkoMobBoss()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1
    def test_creates_goblin_tokens(self):
        game = _make_game()
        p1 = game.players[0]
        krenko = KrenkoMobBoss(owner=p1, controller=p1)
        _place_on_battlefield(game, krenko, p1)
        krenko.is_tapped = False
        abilities = krenko.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, krenko)
        ab.effect(game)
        bf = game.get_battlefield(p1).get_all()
        tokens = [x for x in bf if x.name == "Goblin" and x is not krenko]
        assert len(tokens) >= 1
