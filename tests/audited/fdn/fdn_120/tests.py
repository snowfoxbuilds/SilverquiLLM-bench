"""Audited tests for FDN 120 — Fiendish Panda."""
from __future__ import annotations
from card_impl import FiendishPanda
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent, GainsLifeTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestFiendishPandaBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = FiendishPanda(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FiendishPanda(owner=None)
        assert card.name == 'Fiendish Panda'

    def test_mana_cost(self) -> None:
        card = FiendishPanda(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{W}{B}')

    def test_power_toughness(self) -> None:
        card = FiendishPanda(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = FiendishPanda(owner=None)
        assert 'Bear' in card.subtypes
        assert 'Demon' in card.subtypes

class TestFiendishPandaLifegain:
    """Lifegain trigger: +1/+1 counter."""

    def test_gets_counter_on_lifegain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        panda = FiendishPanda(owner=p1, controller=p1)
        game.get_battlefield(p1).add(panda)
        panda.register_triggers(game)
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=3))
        _resolve_stack(game)
        assert getattr(panda, 'plus_one_counters', 0) >= 1

    def test_no_counter_when_opponent_gains_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        panda = FiendishPanda(owner=p1, controller=p1)
        game.get_battlefield(p1).add(panda)
        panda.register_triggers(game)
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p2, amount=3))
        _resolve_stack(game)
        assert getattr(panda, 'plus_one_counters', 0) == 0

class TestFiendishPandaDies:
    """Death trigger: return non-Bear creature from graveyard."""

    def test_returns_creature_on_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        panda = FiendishPanda(owner=p1, controller=p1)
        game.get_battlefield(p1).add(panda)
        target = Creature(name='Goblin', base_power=2, base_toughness=2, mana_cost=ManaCost.parse('{1}{R}'), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        panda.register_triggers(game)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=panda))
        _resolve_stack(game)
        assert game.get_battlefield(p1).contains(target)

    def test_does_not_return_bear(self) -> None:
        game = create_game()
        p1 = game.players[0]
        panda = FiendishPanda(owner=p1, controller=p1)
        game.get_battlefield(p1).add(panda)
        bear = Creature(name='Grizzly Bear', base_power=2, base_toughness=2, subtypes={'Bear'}, mana_cost=ManaCost.parse('{1}{G}'), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(bear)
        panda.register_triggers(game)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=panda))
        _resolve_stack(game)
        assert not game.get_battlefield(p1).contains(bear)
        assert p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_respects_power_limit(self) -> None:
        game = create_game()
        p1 = game.players[0]
        panda = FiendishPanda(owner=p1, controller=p1)
        game.get_battlefield(p1).add(panda)
        big = Creature(name='Angel', base_power=4, base_toughness=4, mana_cost=ManaCost.parse('{3}{W}{W}'), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(big)
        panda.register_triggers(game)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=panda))
        _resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(big)
