"""Audited tests for FDN 108 — Needletooth Pack."""
from __future__ import annotations
from card_impl import NeedletoothPack
from engine.card import Creature
from engine.player import DeterministicPlayer
from engine.types import ManaCost
from test_utils import create_game
from engine.events import EndStepTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestNeedletoothPackBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = NeedletoothPack(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = NeedletoothPack(owner=None)
        assert card.name == 'Needletooth Pack'

    def test_mana_cost(self) -> None:
        card = NeedletoothPack(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{G}{G}')

    def test_power_toughness(self) -> None:
        card = NeedletoothPack(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 5

    def test_subtypes(self) -> None:
        card = NeedletoothPack(owner=None)
        assert 'Dinosaur' in card.subtypes

class TestNeedletoothPackMorbid:
    """Morbid: end step, put two +1/+1 counters on target creature you control."""

    def test_puts_two_counters_when_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pack = NeedletoothPack(owner=p1, controller=p1)
        game.get_battlefield(p1).add(pack)
        pack.register_triggers(game)
        game.creature_died_this_turn = True
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(pack)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert pack.plus_one_counters == 2
        assert pack._base_plus_one_counters == 2

    def test_no_counters_when_no_creature_died(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pack = NeedletoothPack(owner=p1, controller=p1)
        game.get_battlefield(p1).add(pack)
        pack.register_triggers(game)
        game.creature_died_this_turn = False
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert pack.plus_one_counters == 0

    def test_can_target_another_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pack = NeedletoothPack(owner=p1, controller=p1)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(pack)
        game.get_battlefield(p1).add(other)
        pack.register_triggers(game)
        game.creature_died_this_turn = True
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(other)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert other.plus_one_counters == 2
        assert other._base_plus_one_counters == 2

    def test_counter_increases_power_and_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pack = NeedletoothPack(owner=p1, controller=p1)
        game.get_battlefield(p1).add(pack)
        pack.register_triggers(game)
        game.creature_died_this_turn = True
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(pack)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert pack.power == 6
        assert pack.toughness == 7
