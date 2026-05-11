"""Audited tests for Scavenging Ooze (FDN collector number 232) — graveyard exile."""
from __future__ import annotations
import pytest
from card_impl import ScavengingOoze
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
class TestScavengingOozeProperties:
    def test_is_creature(self):
        assert isinstance(ScavengingOoze(), Creature)
    def test_power_toughness(self):
        c = ScavengingOoze()
        assert c.base_power == 2 and c.base_toughness == 2
    def test_mana_cost(self):
        assert ScavengingOoze().mana_cost == ManaCost.parse("{1}{G}")

@pytest.mark.ability
class TestScavengingOozeAbility:
    def test_has_activated_ability(self):
        c = ScavengingOoze()
        abilities = c.get_activated_abilities()
        assert len(abilities) >= 1

    def test_cost_pays_green(self):
        game = _make_game()
        p1 = game.players[0]
        c = ScavengingOoze(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is True

    def test_cost_fails_without_green(self):
        game = _make_game()
        p1 = game.players[0]
        c = ScavengingOoze(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        # No mana
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        result = ab.cost(game, c)
        assert result is False

    def test_exile_creature_card_gains_counter_and_life(self):
        game = _make_game()
        p1, p2 = game.players
        c = ScavengingOoze(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        # Put a creature card in opponent's graveyard
        from engine.card import CardType
        victim = Creature(name="DeadGuy", owner=p2, controller=p2, base_power=1, base_toughness=1)
        victim.card_types = {CardType.CREATURE}
        p2.zones[Zone.GRAVEYARD].add(victim)
        c._current_target = victim
        p1.mana_pool.add(ManaType.GREEN, 1)
        life_before = p1.life
        counters_before = getattr(c, "plus_one_counters", 0)
        abilities = c.get_activated_abilities()
        ab = abilities[0]
        ab.cost(game, c)
        ab.effect(game)
        assert getattr(c, "plus_one_counters", 0) == counters_before + 1
        assert p1.life == life_before + 1
