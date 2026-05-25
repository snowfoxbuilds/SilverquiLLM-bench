"""Audited tests for FDN 126 — Zimone, Paradox Sculptor."""
from __future__ import annotations
from card_impl import ZimoneParadoxSculptor
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import BeginningOfCombatTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestZimoneBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ZimoneParadoxSculptor(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ZimoneParadoxSculptor(owner=None)
        assert card.name == 'Zimone, Paradox Sculptor'

    def test_mana_cost(self) -> None:
        card = ZimoneParadoxSculptor(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{G}{U}')

    def test_power_toughness(self) -> None:
        card = ZimoneParadoxSculptor(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        card = ZimoneParadoxSculptor(owner=None)
        assert 'Legendary' in getattr(card, 'supertypes', set())

    def test_subtypes(self) -> None:
        card = ZimoneParadoxSculptor(owner=None)
        assert 'Human' in card.subtypes
        assert 'Wizard' in card.subtypes

class TestZimoneCombatTrigger:
    """Beginning of combat: +1/+1 counters on up to two creatures."""

    def test_adds_counter_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        zimone = ZimoneParadoxSculptor(owner=p1, controller=p1)
        ally = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(zimone)
        game.get_battlefield(p1).add(ally)
        zimone.register_triggers(game)
        game.active_player_index = 0
        p1._script.appendleft(ally)
        p1._script.appendleft(zimone)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
        _resolve_stack(game)
        assert getattr(ally, 'plus_one_counters', 0) >= 1

    def test_adds_counters_to_two_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        zimone = ZimoneParadoxSculptor(owner=p1, controller=p1)
        ally1 = Creature(name='Bear1', base_power=2, base_toughness=2, owner=p1, controller=p1)
        ally2 = Creature(name='Bear2', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(zimone)
        game.get_battlefield(p1).add(ally1)
        game.get_battlefield(p1).add(ally2)
        zimone.register_triggers(game)
        game.active_player_index = 0
        p1._script.appendleft(ally1)
        p1._script.appendleft(ally2)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
        _resolve_stack(game)
        assert getattr(ally1, 'plus_one_counters', 0) >= 1
        assert getattr(ally2, 'plus_one_counters', 0) >= 1

class TestZimoneActivatedAbility:
    """Activated ability: double counters."""

    def test_has_activated_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        zimone = ZimoneParadoxSculptor(owner=p1, controller=p1)
        game.get_battlefield(p1).add(zimone)
        abilities = zimone.get_activated_abilities(game)
        assert len(abilities) >= 1

    def test_ability_has_tap_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        zimone = ZimoneParadoxSculptor(owner=p1, controller=p1)
        game.get_battlefield(p1).add(zimone)
        abilities = zimone.get_activated_abilities(game)
        assert abilities[0].tap_cost is True

    def test_doubles_counters_on_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        zimone = ZimoneParadoxSculptor(owner=p1, controller=p1)
        ally = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        ally.plus_one_counters = 2
        game.get_battlefield(p1).add(zimone)
        game.get_battlefield(p1).add(ally)
        p1.mana_pool.add(ManaType.GREEN, 1)
        p1.mana_pool.add(ManaType.BLUE, 1)
        abilities = zimone.get_activated_abilities(game)
        p1._script.appendleft(ally)
        abilities[0].effect(game)
        assert ally.plus_one_counters >= 4
