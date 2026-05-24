"""Audited tests for FDN 112 — Spinner of Souls."""
from __future__ import annotations
from card_impl import SpinnerOfSouls
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import CreatureDiesTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestSpinnerOfSoulsBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SpinnerOfSouls(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SpinnerOfSouls(owner=None)
        assert card.name == 'Spinner of Souls'

    def test_mana_cost(self) -> None:
        card = SpinnerOfSouls(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{G}')

    def test_power_toughness(self) -> None:
        card = SpinnerOfSouls(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_has_reach(self) -> None:
        card = SpinnerOfSouls(owner=None)
        assert Keyword.REACH in card.keywords

    def test_subtypes(self) -> None:
        card = SpinnerOfSouls(owner=None)
        assert 'Spider' in card.subtypes
        assert 'Spirit' in card.subtypes

class TestSpinnerOfSoulsDiesTrigger:
    """When another nontoken creature you control dies, reveal until creature found."""

    def test_reveals_and_finds_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        game.get_battlefield(p1).add(spinner)
        spinner.register_triggers(game)
        noncreature = Instant(name='Shock', owner=p1)
        creature_in_lib = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.LIBRARY].add(creature_in_lib)
        p1.zones[Zone.LIBRARY].add(noncreature)
        dying = Creature(name='Dying', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=dying, controller=p1))
        _resolve_stack(game)
        assert p1.zones[Zone.HAND].contains(creature_in_lib)

    def test_noncreature_cards_go_to_bottom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        game.get_battlefield(p1).add(spinner)
        spinner.register_triggers(game)
        noncreature = Instant(name='Shock', owner=p1)
        creature_in_lib = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.LIBRARY].add(creature_in_lib)
        p1.zones[Zone.LIBRARY].add(noncreature)
        dying = Creature(name='Dying', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=dying, controller=p1))
        _resolve_stack(game)
        assert p1.zones[Zone.LIBRARY].contains(noncreature)

    def test_self_dying_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        game.get_battlefield(p1).add(spinner)
        spinner.register_triggers(game)
        creature_in_lib = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.LIBRARY].add(creature_in_lib)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=spinner, controller=p1))
        _resolve_stack(game)
        assert not p1.zones[Zone.HAND].contains(creature_in_lib)

    def test_token_dying_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        game.get_battlefield(p1).add(spinner)
        spinner.register_triggers(game)
        creature_in_lib = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.LIBRARY].add(creature_in_lib)
        token = Creature(name='Token', base_power=1, base_toughness=1, owner=p1, controller=p1)
        token.is_token = True
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=token, controller=p1))
        _resolve_stack(game)
        assert not p1.zones[Zone.HAND].contains(creature_in_lib)

    def test_opponent_creature_dying_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spinner = SpinnerOfSouls(owner=p1, controller=p1)
        game.get_battlefield(p1).add(spinner)
        spinner.register_triggers(game)
        creature_in_lib = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.LIBRARY].add(creature_in_lib)
        opp_creature = Creature(name='Opp', base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=opp_creature, controller=p2))
        _resolve_stack(game)
        assert not p1.zones[Zone.HAND].contains(creature_in_lib)
