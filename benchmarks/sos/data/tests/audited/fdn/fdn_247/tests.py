"""Audited tests for FDN 247 — Tatyova, Benthic Druid."""
from __future__ import annotations
from card_impl import TatyovaBenthicDruid
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestTatyovaBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = TatyovaBenthicDruid(owner=None)
        assert card.name == 'Tatyova, Benthic Druid'

    def test_mana_cost(self) -> None:
        card = TatyovaBenthicDruid(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{G}{U}')

    def test_power_toughness(self) -> None:
        card = TatyovaBenthicDruid(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_is_legendary(self) -> None:
        card = TatyovaBenthicDruid(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = TatyovaBenthicDruid(owner=None)
        assert 'Merfolk' in card.subtypes
        assert 'Druid' in card.subtypes

class TestTatyovaLandfall:
    """Whenever a land enters under your control, gain 1 life and draw."""

    def test_gains_life_on_land_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        tatyova = TatyovaBenthicDruid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(tatyova)
        tatyova.register_triggers(game)
        p1.zones[Zone.LIBRARY].add(CardImpl(name='Card', owner=p1))
        land = CardImpl(name='Forest', owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p1).add(land)
        starting_life = p1.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        assert p1.life == starting_life + 1

    def test_draws_card_on_land_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        tatyova = TatyovaBenthicDruid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(tatyova)
        tatyova.register_triggers(game)
        p1.zones[Zone.LIBRARY].add(CardImpl(name='Card', owner=p1))
        land = CardImpl(name='Forest', owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p1).add(land)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before + 1

    def test_non_land_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        tatyova = TatyovaBenthicDruid(owner=p1, controller=p1)
        game.get_battlefield(p1).add(tatyova)
        tatyova.register_triggers(game)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        starting_life = p1.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=creature))
        _resolve_stack(game)
        assert p1.life == starting_life
