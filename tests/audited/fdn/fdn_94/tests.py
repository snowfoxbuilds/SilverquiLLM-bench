"""Audited tests for FDN 94 — Slumbering Cerberus."""
from __future__ import annotations
from card_impl import SlumberingCerberus
from engine.card import Creature
from engine.types import ManaCost, Zone
from tests.test_utils import create_game
from engine.events import EndStepTriggeredEvent

class TestSlumberingCerberusBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SlumberingCerberus(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SlumberingCerberus(owner=None)
        assert card.name == 'Slumbering Cerberus'

    def test_mana_cost(self) -> None:
        card = SlumberingCerberus(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{R}')

    def test_power_toughness(self) -> None:
        card = SlumberingCerberus(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = SlumberingCerberus(owner=None)
        assert 'Dog' in card.subtypes

    def test_skip_untap_set(self) -> None:
        card = SlumberingCerberus(owner=None)
        assert card.skip_untap is True

class TestSlumberingCerberusMorbidTrigger:
    """Morbid — end step: untap if a creature died this turn."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_untaps_when_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingCerberus(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.is_tapped = True
        card.register_triggers(game)
        game.creature_died_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        self._resolve_stack(game)
        assert card.is_tapped is False

    def test_stays_tapped_when_no_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingCerberus(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.is_tapped = True
        card.register_triggers(game)
        game.creature_died_this_turn = False
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        self._resolve_stack(game)
        assert card.is_tapped is True

    def test_already_untapped_stays_untapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingCerberus(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.is_tapped = False
        card.register_triggers(game)
        game.creature_died_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        self._resolve_stack(game)
        assert card.is_tapped is False
