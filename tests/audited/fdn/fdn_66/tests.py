"""Audited tests for FDN 66 — Nine-Lives Familiar."""
from __future__ import annotations
from card_impl import NineLivesFamiliar
from engine.card import Creature
from engine.types import ManaCost, Zone
from tests.test_utils import create_game
from engine.events import CreatureDiesTriggeredEvent, EntersBattlefieldTriggeredEvent

class TestNineLivesFamiliarBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = NineLivesFamiliar(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = NineLivesFamiliar(owner=None)
        assert card.name == 'Nine-Lives Familiar'

    def test_mana_cost(self) -> None:
        card = NineLivesFamiliar(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{B}{B}')

    def test_power_toughness(self) -> None:
        card = NineLivesFamiliar(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = NineLivesFamiliar(owner=None)
        assert 'Cat' in card.subtypes

class TestNineLivesFamiliarCounters:
    """Enters with 8 revival counters; returns on death with one fewer."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_etb_gives_eight_revival_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=card))
        self._resolve_stack(game)
        assert card.revival_counters == 8

    def test_returns_on_death_with_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        card.revival_counters = 8
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert game.get_battlefield(p1).contains(card)
        assert card.revival_counters == 7

    def test_does_not_return_with_zero_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        card.revival_counters = 0
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert not game.get_battlefield(p1).contains(card)

    def test_decrements_counter_each_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        card.revival_counters = 2
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert card.revival_counters == 1
