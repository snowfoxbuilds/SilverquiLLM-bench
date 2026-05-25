"""Audited tests for FDN 68 — Sanguine Syphoner."""
from __future__ import annotations
from card_impl import SanguineSyphoner
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game
from engine.events import AttacksTriggeredEvent

class TestSanguineSyphonerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SanguineSyphoner(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SanguineSyphoner(owner=None)
        assert card.name == 'Sanguine Syphoner'

    def test_mana_cost(self) -> None:
        card = SanguineSyphoner(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{B}')

    def test_power_toughness(self) -> None:
        card = SanguineSyphoner(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = SanguineSyphoner(owner=None)
        assert 'Vampire' in card.subtypes
        assert 'Warlock' in card.subtypes

class TestSanguineSyphonerAttackTrigger:
    """Whenever attacks, each opponent loses 1 life and you gain 1."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_opponent_loses_1_life_on_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SanguineSyphoner(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert p2.life == p2_life_before - 1

    def test_controller_gains_1_life_on_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SanguineSyphoner(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        p1_life_before = p1.life
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert p1.life == p1_life_before + 1

    def test_does_not_trigger_for_other_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SanguineSyphoner(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        other = Creature(name='Other', base_power=2, base_toughness=2, owner=p1, controller=p1)
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=other))
        self._resolve_stack(game)
        assert p2.life == p2_life_before
