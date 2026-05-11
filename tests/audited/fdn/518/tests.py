"""Audited tests for Crossway Troublemakers (FDN collector number 518) — other creature dies trigger."""
from __future__ import annotations
import pytest
from card_impl import CrosswayTroublemakers
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
class TestCrosswayTroublemakersProperties:
    def test_is_creature(self):
        assert isinstance(CrosswayTroublemakers(), Creature)
    def test_power_toughness(self):
        c = CrosswayTroublemakers()
        assert c.base_power == 5 and c.base_toughness == 5
    def test_mana_cost(self):
        assert CrosswayTroublemakers().mana_cost == ManaCost.parse("{5}{B}")

@pytest.mark.ability
class TestCrosswayTroublemakersDeath:
    def test_vampire_dying_pays_life_and_draws(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        ct = CrosswayTroublemakers(owner=p1, controller=p1)
        _place_on_battlefield(game, ct, p1)
        ct.register_triggers(game)
        vampire = Creature(name="Vampire", owner=p1, controller=p1,
                           base_power=1, base_toughness=1, subtypes={"Vampire"})
        hand_before = len(p1.zones[Zone.HAND].get_all())
        life_before = p1.life
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES,
                                        {"creature": vampire, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        # Should pay 2 life and draw a card
        assert p1.life == life_before - 2
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_non_vampire_dying_does_not_trigger(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        ct = CrosswayTroublemakers(owner=p1, controller=p1)
        _place_on_battlefield(game, ct, p1)
        ct.register_triggers(game)
        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2, subtypes={"Bear"})
        hand_before = len(p1.zones[Zone.HAND].get_all())
        life_before = p1.life
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES,
                                        {"creature": bear, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        # Non-Vampire should not trigger
        assert p1.life == life_before
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before

    def test_opponent_vampire_dying_does_not_trigger(self):
        game = _make_game()
        p1, p2 = game.players
        _add_library(p1, 5)
        ct = CrosswayTroublemakers(owner=p1, controller=p1)
        _place_on_battlefield(game, ct, p1)
        ct.register_triggers(game)
        opp_vamp = Creature(name="OppVamp", owner=p2, controller=p2,
                            base_power=1, base_toughness=1, subtypes={"Vampire"})
        hand_before = len(p1.zones[Zone.HAND].get_all())
        life_before = p1.life
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES,
                                        {"creature": opp_vamp, "controller": p2})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        # Opponent's Vampire should not trigger (must be "you control")
        assert p1.life == life_before
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before
