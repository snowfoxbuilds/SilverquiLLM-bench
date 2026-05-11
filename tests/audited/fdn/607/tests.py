"""Audited tests for Kalastria Highborn (FDN collector number 607) — vampire death trigger."""
from __future__ import annotations
import pytest
from card_impl import KalastriaHighborn
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Phase, Zone

def _make_game():
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = Phase.PRECOMBAT_MAIN
    game.active_player_index = 0
    return game

def _add_library(player, n):
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards

def _place_on_battlefield(game, creature, player):
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)

def _simulate_death(game, creature, controller=None):
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": creature, "controller": controller})
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)

@pytest.mark.basic
class TestKalastriaHighbornProperties:
    def test_is_creature(self):
        assert isinstance(KalastriaHighborn(), Creature)
    def test_power_toughness(self):
        c = KalastriaHighborn()
        assert c.base_power == 2 and c.base_toughness == 2

@pytest.mark.ability
class TestKalastriaHighbornDeath:
    def test_own_death_drains_opponent(self):
        game = _make_game()
        p1, p2 = game.players
        c = KalastriaHighborn(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        p1_life_before = p1.life
        p2_life_before = p2.life
        _simulate_death(game, c)
        # Should drain: controller gains 2 life, opponent loses 2 life
        assert p1.life == p1_life_before + 2
        assert p2.life == p2_life_before - 2

    def test_another_vampire_death_drains(self):
        game = _make_game()
        p1, p2 = game.players
        c = KalastriaHighborn(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.register_triggers(game)
        other_vamp = Creature(name="OtherVamp", owner=p1, controller=p1,
                              base_power=1, base_toughness=1, subtypes={"Vampire"})
        p1_life_before = p1.life
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES,
                                        {"creature": other_vamp, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert p1.life == p1_life_before + 2
        assert p2.life == p2_life_before - 2

    def test_non_vampire_death_does_not_trigger(self):
        game = _make_game()
        p1, p2 = game.players
        c = KalastriaHighborn(owner=p1, controller=p1)
        _place_on_battlefield(game, c, p1)
        c.register_triggers(game)
        non_vamp = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2, subtypes={"Bear"})
        p1_life_before = p1.life
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES,
                                        {"creature": non_vamp, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        # Non-Vampire dying should not trigger drain
        assert p1.life == p1_life_before
        assert p2.life == p2_life_before
