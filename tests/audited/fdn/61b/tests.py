"""Audited tests for High-Society Hunter (FDN collector number 61) — death trigger."""
from __future__ import annotations
import pytest
from card_impl import HighSocietyHunter
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
class TestHighSocietyHunterProperties:
    def test_is_creature(self):
        assert isinstance(HighSocietyHunter(), Creature)
    def test_power_toughness(self):
        c = HighSocietyHunter()
        assert c.base_power == 5 and c.base_toughness == 3
    def test_has_flying(self):
        assert Keyword.FLYING in HighSocietyHunter().keywords

@pytest.mark.ability
class TestHighSocietyHunterDeath:
    def test_another_nontoken_creature_dying_draws_card(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        _place_on_battlefield(game, hunter, p1)
        hunter.register_triggers(game)
        other = Creature(name="Other", owner=p1, controller=p1, base_power=1, base_toughness=1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": other, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_self_dying_does_not_draw(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        _place_on_battlefield(game, hunter, p1)
        hunter.register_triggers(game)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": hunter, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        # "another" — self dying should NOT trigger draw
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before

@pytest.mark.edge
class TestHighSocietyHunterEdge:
    def test_token_creature_dying_does_not_draw(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 5)
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        _place_on_battlefield(game, hunter, p1)
        hunter.register_triggers(game)
        token = Creature(name="Token", owner=p1, controller=p1, base_power=1, base_toughness=1)
        token.is_token = True
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, EventType.CREATURE_DIES, {"creature": token, "controller": p1})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        # Token creatures should not trigger the draw (nontoken only)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before
