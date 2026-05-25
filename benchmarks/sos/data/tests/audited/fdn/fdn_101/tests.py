"""Audited tests for FDN 101 — Cackling Prowler."""
from __future__ import annotations
from card_impl import CacklingProwler
from engine.card import Creature
from engine.types import Keyword, ManaCost
from test_utils import create_game
from engine.events import EndStepTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestCacklingProwlerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = CacklingProwler(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CacklingProwler(owner=None)
        assert card.name == 'Cackling Prowler'

    def test_mana_cost(self) -> None:
        card = CacklingProwler(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{G}')

    def test_power_toughness(self) -> None:
        card = CacklingProwler(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_has_ward(self) -> None:
        card = CacklingProwler(owner=None)
        assert Keyword.WARD in card.keywords

    def test_subtypes(self) -> None:
        card = CacklingProwler(owner=None)
        assert 'Hyena' in card.subtypes
        assert 'Rogue' in card.subtypes

class TestCacklingProwlerMorbid:
    """Morbid: end step +1/+1 counter if a creature died this turn."""

    def test_gets_counter_when_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        prowler = CacklingProwler(owner=p1, controller=p1)
        game.get_battlefield(p1).add(prowler)
        prowler.register_triggers(game)
        game.creature_died_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert prowler.plus_one_counters == 1
        assert prowler._base_plus_one_counters == 1

    def test_no_counter_when_no_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        prowler = CacklingProwler(owner=p1, controller=p1)
        game.get_battlefield(p1).add(prowler)
        prowler.register_triggers(game)
        game.creature_died_this_turn = False
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert prowler.plus_one_counters == 0

    def test_counter_increases_power_and_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        prowler = CacklingProwler(owner=p1, controller=p1)
        game.get_battlefield(p1).add(prowler)
        prowler.register_triggers(game)
        game.creature_died_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert prowler.power == 5
        assert prowler.toughness == 4
