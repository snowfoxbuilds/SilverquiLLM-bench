"""Audited tests for FDN 149 — Youthful Valkyrie."""
from __future__ import annotations
from card_impl import YouthfulValkyrie
from engine.card import Creature
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestYouthfulValkyrieBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = YouthfulValkyrie(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = YouthfulValkyrie(owner=None)
        assert card.name == 'Youthful Valkyrie'

    def test_mana_cost(self) -> None:
        card = YouthfulValkyrie(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{W}')

    def test_power_toughness(self) -> None:
        card = YouthfulValkyrie(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = YouthfulValkyrie(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_angel_subtype(self) -> None:
        card = YouthfulValkyrie(owner=None)
        assert 'Angel' in card.subtypes

class TestYouthfulValkyrieTrigger:
    """Whenever another Angel you control enters, +1/+1 counter."""

    def test_another_angel_gives_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        valk = YouthfulValkyrie(owner=p1, controller=p1)
        game.get_battlefield(p1).add(valk)
        valk.register_triggers(game)
        other_angel = Creature(name='Test Angel', base_power=2, base_toughness=2, owner=p1, controller=p1, subtypes={'Angel'})
        game.get_battlefield(p1).add(other_angel)
        initial = getattr(valk, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=other_angel))
        _resolve_stack(game)
        assert getattr(valk, 'plus_one_counters', 0) == initial + 1

    def test_self_entering_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        valk = YouthfulValkyrie(owner=p1, controller=p1)
        game.get_battlefield(p1).add(valk)
        valk.register_triggers(game)
        initial = getattr(valk, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=valk))
        _resolve_stack(game)
        assert getattr(valk, 'plus_one_counters', 0) == initial

    def test_non_angel_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        valk = YouthfulValkyrie(owner=p1, controller=p1)
        game.get_battlefield(p1).add(valk)
        valk.register_triggers(game)
        non_angel = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1, subtypes={'Bear'})
        game.get_battlefield(p1).add(non_angel)
        initial = getattr(valk, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=non_angel))
        _resolve_stack(game)
        assert getattr(valk, 'plus_one_counters', 0) == initial

    def test_opponent_angel_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        valk = YouthfulValkyrie(owner=p1, controller=p1)
        game.get_battlefield(p1).add(valk)
        valk.register_triggers(game)
        opp_angel = Creature(name='Opp Angel', base_power=2, base_toughness=2, owner=p2, controller=p2, subtypes={'Angel'})
        game.get_battlefield(p2).add(opp_angel)
        initial = getattr(valk, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=opp_angel))
        _resolve_stack(game)
        assert getattr(valk, 'plus_one_counters', 0) == initial
