"""Audited tests for FDN 37 — Erudite Wizard."""
from __future__ import annotations
from card_impl import EruditeWizard
from engine.card import Creature
from engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import DrawsCardTriggeredEvent

class TestEruditeWizardBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = EruditeWizard(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EruditeWizard(owner=None)
        assert card.name == 'Erudite Wizard'

    def test_mana_cost(self) -> None:
        card = EruditeWizard(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{U}')

    def test_power_toughness(self) -> None:
        card = EruditeWizard(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = EruditeWizard(owner=None)
        assert 'Human' in card.subtypes
        assert 'Wizard' in card.subtypes

class TestEruditeWizardSecondDrawTrigger:
    """Whenever you draw your second card each turn, put a +1/+1 counter."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        wizard = EruditeWizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)
        wizard.register_triggers(game)
        game.turn_number = 1
        return (game, wizard, p1)

    def test_no_counter_on_first_draw(self) -> None:
        game, wizard, p1 = self._setup()
        initial = wizard.plus_one_counters
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        self._resolve_stack(game)
        assert wizard.plus_one_counters == initial

    def test_counter_on_second_draw(self) -> None:
        game, wizard, p1 = self._setup()
        initial = wizard.plus_one_counters
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        self._resolve_stack(game)
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        self._resolve_stack(game)
        assert wizard.plus_one_counters == initial + 1

    def test_no_counter_on_third_draw_same_turn(self) -> None:
        game, wizard, p1 = self._setup()
        initial = wizard.plus_one_counters
        for _ in range(3):
            game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
            self._resolve_stack(game)
        assert wizard.plus_one_counters == initial + 1

    def test_resets_on_new_turn(self) -> None:
        game, wizard, p1 = self._setup()
        initial = wizard.plus_one_counters
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        self._resolve_stack(game)
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        self._resolve_stack(game)
        assert wizard.plus_one_counters == initial + 1
        game.turn_number = 2
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        self._resolve_stack(game)
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        self._resolve_stack(game)
        assert wizard.plus_one_counters == initial + 2

    def test_no_counter_on_opponent_draw(self) -> None:
        game, wizard, p1 = self._setup()
        p2 = game.players[1]
        initial = wizard.plus_one_counters
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p2))
        self._resolve_stack(game)
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p2))
        self._resolve_stack(game)
        assert wizard.plus_one_counters == initial
