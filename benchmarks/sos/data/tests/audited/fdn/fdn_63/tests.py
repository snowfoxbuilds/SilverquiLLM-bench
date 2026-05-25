"""Audited tests for FDN 63 — Infernal Vessel."""
from __future__ import annotations
from card_impl import InfernalVessel
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game
from engine.events import CreatureDiesTriggeredEvent

class TestInfernalVesselBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = InfernalVessel(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = InfernalVessel(owner=None)
        assert card.name == 'Infernal Vessel'

    def test_mana_cost(self) -> None:
        card = InfernalVessel(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{B}')

    def test_power_toughness(self) -> None:
        card = InfernalVessel(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = InfernalVessel(owner=None)
        assert 'Human' in card.subtypes
        assert 'Cleric' in card.subtypes

class TestInfernalVesselDeathTrigger:
    """When dies (if not Demon), return with two +1/+1 counters as Demon."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_returns_to_battlefield_on_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfernalVessel(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert game.get_battlefield(p1).contains(card)

    def test_gains_demon_subtype(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfernalVessel(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert 'Demon' in card.subtypes

    def test_keeps_original_subtypes(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfernalVessel(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert 'Human' in card.subtypes
        assert 'Cleric' in card.subtypes

    def test_does_not_trigger_if_already_demon(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfernalVessel(owner=p1, controller=p1)
        card.subtypes = card.subtypes | {'Demon'}
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        bf_before = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after == bf_before

    def test_gets_plus_one_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfernalVessel(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.get_battlefield(p1).remove(card)
        p1.zones[Zone.GRAVEYARD].add(card)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=card))
        self._resolve_stack(game)
        counters = getattr(card, 'plus_one_counters', 0)
        assert counters == 2
