"""Audited tests for FDN 185 — Stromkirk Bloodthief."""
from __future__ import annotations
from card_impl import StromkirkBloodthief
from engine.card import Creature
from engine.types import ManaCost
from test_utils import create_game
from engine.events import EndStepTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestStromkirkBloodthiefBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = StromkirkBloodthief(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = StromkirkBloodthief(owner=None)
        assert card.name == 'Stromkirk Bloodthief'

    def test_mana_cost(self) -> None:
        card = StromkirkBloodthief(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{B}')

    def test_power_toughness(self) -> None:
        card = StromkirkBloodthief(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = StromkirkBloodthief(owner=None)
        assert 'Vampire' in card.subtypes
        assert 'Rogue' in card.subtypes

class TestStromkirkBloodthiefTrigger:
    """At beginning of your end step, if opponent lost life, +1/+1 counter on Vampire."""

    def test_does_not_trigger_if_no_life_lost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        game.state = game
        bloodthief = StromkirkBloodthief(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bloodthief)
        bloodthief.register_triggers(game)
        game.active_player_index = 0
        p2.life_lost_this_turn = 0
        counters_before = getattr(bloodthief, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        counters_after = getattr(bloodthief, 'plus_one_counters', 0)
        assert counters_after == counters_before

    def test_does_not_trigger_on_opponent_end_step(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bloodthief = StromkirkBloodthief(owner=p1, controller=p1)
        game.get_battlefield(p1).add(bloodthief)
        bloodthief.register_triggers(game)
        game.active_player_index = 1
        p1.life_lost_this_turn = 5
        counters_before = getattr(bloodthief, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        counters_after = getattr(bloodthief, 'plus_one_counters', 0)
        assert counters_after == counters_before
