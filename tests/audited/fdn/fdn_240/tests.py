"""Audited tests for FDN 240 — Good-Fortune Unicorn."""

from __future__ import annotations

from card_impl import GoodFortuneUnicorn
from engine.card import Creature
from engine.triggers import EventType
from engine.types import CardType, ManaCost
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestGoodFortuneUnicornBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = GoodFortuneUnicorn(owner=None)
        assert card.name == "Good-Fortune Unicorn"

    def test_mana_cost(self) -> None:
        card = GoodFortuneUnicorn(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{G}{W}")

    def test_power_toughness(self) -> None:
        card = GoodFortuneUnicorn(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = GoodFortuneUnicorn(owner=None)
        assert "Unicorn" in card.subtypes


class TestGoodFortuneUnicornTrigger:
    """Whenever another creature enters, put +1/+1 counter on it."""

    def test_puts_counter_on_entering_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        unicorn = GoodFortuneUnicorn(owner=p1, controller=p1)
        game.get_battlefield(p1).add(unicorn)
        unicorn.register_triggers(game)
        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": other})
        _resolve_stack(game)
        assert other.plus_one_counters >= 1

    def test_self_entering_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        unicorn = GoodFortuneUnicorn(owner=p1, controller=p1)
        game.get_battlefield(p1).add(unicorn)
        unicorn.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": unicorn})
        _resolve_stack(game)
        assert getattr(unicorn, "plus_one_counters", 0) == 0

    def test_opponent_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        unicorn = GoodFortuneUnicorn(owner=p1, controller=p1)
        game.get_battlefield(p1).add(unicorn)
        unicorn.register_triggers(game)
        opp = Creature(name="Opp", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": opp})
        _resolve_stack(game)
        assert getattr(opp, "plus_one_counters", 0) == 0

