"""Audited tests for FDN 141 — Giada, Font of Hope."""
from __future__ import annotations
from card_impl import GiadaFontOfHope
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestGiadaFontOfHopeBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert card.name == 'Giada, Font of Hope'

    def test_mana_cost(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{W}')

    def test_power_toughness(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_flying(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_is_legendary(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert getattr(card, 'is_legendary', False)

    def test_angel_subtype(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert 'Angel' in card.subtypes

class TestGiadaAngelETB:
    """Other Angels enter with +1/+1 counters equal to your Angel count."""

    def test_other_angel_gets_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giada = GiadaFontOfHope(owner=p1, controller=p1)
        game.get_battlefield(p1).add(giada)
        giada.register_triggers(game)
        other_angel = Creature(name='Test Angel', base_power=2, base_toughness=2, owner=p1, controller=p1, subtypes={'Angel'})
        game.get_battlefield(p1).add(other_angel)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=other_angel))
        _resolve_stack(game)
        assert getattr(other_angel, 'plus_one_counters', 0) >= 1

    def test_non_angel_does_not_get_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giada = GiadaFontOfHope(owner=p1, controller=p1)
        game.get_battlefield(p1).add(giada)
        giada.register_triggers(game)
        non_angel = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1, subtypes={'Bear'})
        game.get_battlefield(p1).add(non_angel)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=non_angel))
        _resolve_stack(game)
        assert getattr(non_angel, 'plus_one_counters', 0) == 0
