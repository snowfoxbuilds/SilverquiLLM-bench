"""Audited tests for FDN 23 — Skyknight Squire."""
from __future__ import annotations
from card_impl import SkyknightSquire
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

class TestSkyknightSquireBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SkyknightSquire(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SkyknightSquire(owner=None)
        assert card.name == 'Skyknight Squire'

    def test_mana_cost(self) -> None:
        card = SkyknightSquire(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{W}')

    def test_power_toughness(self) -> None:
        card = SkyknightSquire(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = SkyknightSquire(owner=None)
        assert 'Cat' in card.subtypes
        assert 'Scout' in card.subtypes

class TestSkyknightSquireETBTrigger:
    """Another creature entering gives +1/+1 counter."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        squire = SkyknightSquire(owner=p1, controller=p1)
        game.get_battlefield(p1).add(squire)
        squire.register_triggers(game)
        return (game, p1, squire)

    def test_another_creature_entering_adds_counter(self) -> None:
        game, p1, squire = self._setup()
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=other, controller=p1))
        self._resolve_stack(game)
        assert getattr(squire, 'plus_one_counters', 0) >= 1

    def test_self_entering_does_not_trigger(self) -> None:
        game, p1, squire = self._setup()
        initial = getattr(squire, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=squire, controller=p1))
        self._resolve_stack(game)
        assert getattr(squire, 'plus_one_counters', 0) == initial

    def test_opponent_creature_does_not_trigger(self) -> None:
        game, p1, squire = self._setup()
        p2 = game.players[1]
        opp = Creature(name='Opp Bear', base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp)
        initial = getattr(squire, 'plus_one_counters', 0)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=opp, controller=p2))
        self._resolve_stack(game)
        assert getattr(squire, 'plus_one_counters', 0) == initial

class TestSkyknightSquireThreshold:
    """3+ counters -> flying and Knight."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup_with_counters(self, count):
        game = create_game()
        p1 = game.players[0]
        squire = SkyknightSquire(owner=p1, controller=p1)
        from engine.game import add_counter
        game.get_battlefield(p1).add(squire)
        squire.register_triggers(game)
        add_counter(game, squire, '+1/+1', count)
        squire._base_plus_one_counters = squire.plus_one_counters
        return (game, p1, squire)

    def test_three_counters_gains_flying(self) -> None:
        game, p1, squire = self._setup_with_counters(3)
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in squire.keywords

    def test_three_counters_becomes_knight(self) -> None:
        game, p1, squire = self._setup_with_counters(3)
        game.effect_manager.apply_all(game)
        assert 'Knight' in squire.subtypes

    def test_two_counters_no_flying(self) -> None:
        game, p1, squire = self._setup_with_counters(2)
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING not in squire.keywords

    def test_two_counters_not_knight(self) -> None:
        game, p1, squire = self._setup_with_counters(2)
        game.effect_manager.apply_all(game)
        assert 'Knight' not in squire.subtypes
