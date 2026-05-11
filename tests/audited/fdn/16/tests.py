"""Audited tests for Helpful Hunter (FDN collector number 16) — ETB draw."""

from __future__ import annotations

import pytest

from card_impl import HelpfulHunter

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


def _simulate_etb(game, creature, controller=None):
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(
        game, EventType.ENTERS_BATTLEFIELD,
        {"permanent": creature, "controller": controller},
    )
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


@pytest.mark.basic
class TestHelpfulHunterProperties:
    def test_is_creature(self):
        c = HelpfulHunter()
        assert isinstance(c, Creature)

    def test_power_toughness(self):
        c = HelpfulHunter()
        assert c.base_power == 1 and c.base_toughness == 1

    def test_name(self):
        assert HelpfulHunter().name == "Helpful Hunter"

    def test_mana_cost(self):
        assert HelpfulHunter().mana_cost == ManaCost.parse("{1}{W}")

    def test_subtypes(self):
        assert "Cat" in HelpfulHunter().subtypes


@pytest.mark.ability
class TestHelpfulHunterETB:
    def test_etb_draws_card(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 3)
        hunter = HelpfulHunter(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_etb(game, hunter)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1

    def test_etb_does_not_affect_opponent(self):
        game = _make_game()
        p1, p2 = game.players
        _add_library(p1, 3)
        hunter = HelpfulHunter(owner=p1, controller=p1)
        opp_hand = len(p2.zones[Zone.HAND].get_all())
        _simulate_etb(game, hunter)
        assert len(p2.zones[Zone.HAND].get_all()) == opp_hand


@pytest.mark.edge
class TestHelpfulHunterEdge:
    def test_no_trigger_for_other_creature(self):
        game = _make_game()
        p1 = game.players[0]
        _add_library(p1, 3)
        hunter = HelpfulHunter(owner=p1, controller=p1)
        hunter.register_triggers(game)
        other = Creature(name="Other", owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD,
            {"permanent": other, "controller": p1},
        )
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before
