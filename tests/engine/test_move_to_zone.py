"""Tests for engine/zones.py — move_to_zone() centralized zone-transition hooks."""
from __future__ import annotations
from typing import Any
import types
import pytest
from engine.card import CardImpl, Creature, Enchantment
from engine.events import CreatureDiesReplacementEvent, CreatureDiesTriggeredEvent, EntersBattlefieldTriggeredEvent, LeavesBattlefieldTriggeredEvent, BeginningOfUpkeepTriggeredEvent, TriggeredEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Zone
from tests.test_utils import create_game, set_board_state

def _make_creature(name: str='TestCreature', power: int=2, toughness: int=2) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)

def _make_enchantment(name: str='TestEnchantment') -> Enchantment:
    return Enchantment(name=name)

def _make_token_creature(name: str='TokenCreature', power: int=1, toughness: int=1) -> Creature:
    token = Creature(name=name, base_power=power, base_toughness=toughness)
    token.is_token = True
    return token

def _record_events(game: Any) -> list[TriggeredEvent]:
    """Monkey-patch the trigger manager to record all fired events."""
    original_fire = game.trigger_manager.fire_event.__func__
    recorded: list[TriggeredEvent] = []

    def recording_fire(self: Any, game: Any, event: TriggeredEvent) -> None:
        recorded.append(event)
        original_fire(self, game, event)
    game.trigger_manager.fire_event = types.MethodType(recording_fire, game.trigger_manager)
    return recorded

class TestMoveToZoneBounce:
    """Bounce a creature from battlefield to hand."""

    def test_bounce_removes_from_battlefield_adds_to_hand(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('Bouncee')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)
        assert not player.zones[Zone.BATTLEFIELD].contains(creature)
        assert player.zones[Zone.HAND].contains(creature)

    def test_bounce_fires_leaves_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('Bouncee')
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)
        assert any((isinstance(e, LeavesBattlefieldTriggeredEvent) for e in recorded))

    def test_bounce_does_not_fire_creature_dies(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('Bouncee')
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)
        assert not any((isinstance(e, CreatureDiesTriggeredEvent) for e in recorded))

    def test_bounce_unregisters_triggers(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('Bouncee')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])
        trigger = TriggerRegistration(event_type=BeginningOfUpkeepTriggeredEvent, condition=None, effect=lambda g: None, source=creature, controller=player)
        game.trigger_manager.register(trigger)
        assert len(game.trigger_manager.get_triggers_for_source(creature)) == 1
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)
        assert len(game.trigger_manager.get_triggers_for_source(creature)) == 0

    def test_bounce_unregisters_replacement_effects(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('Bouncee')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])
        repl = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=creature, condition=None, replacement=lambda g, event: event, controller=player)
        game.replacement_manager.register(repl)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)
        remaining = [r for r in game.replacement_manager._effects if r.source is creature]
        assert len(remaining) == 0

class TestMoveToZoneETB:
    """Enter the battlefield: hand to battlefield."""

    def test_etb_fires_enters_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('ETBCreature')
        set_board_state(game, 0, hand=[creature])
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)
        assert any((isinstance(e, EntersBattlefieldTriggeredEvent) for e in recorded))

    def test_etb_calls_register_triggers(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        registered = []

        class TriggerCreature(Creature):

            def register_triggers(self, game: Any) -> None:
                registered.append(True)
        creature = TriggerCreature(name='TriggerBear', base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[creature])
        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)
        assert len(registered) == 1

    def test_etb_calls_register_replacement_effects(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        registered = []

        class ReplCreature(Creature):

            def register_replacement_effects(self, game: Any) -> None:
                registered.append(True)
        creature = ReplCreature(name='ReplBear', base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[creature])
        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)
        assert len(registered) == 1

    def test_etb_adds_to_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('ETBCreature')
        player = game.players[0]
        set_board_state(game, 0, hand=[creature])
        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)
        assert player.zones[Zone.BATTLEFIELD].contains(creature)
        assert not player.zones[Zone.HAND].contains(creature)

class TestMoveToZoneDeath:
    """Creature dying: battlefield to graveyard."""

    def test_death_fires_leaves_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('DyingCreature')
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert any((isinstance(e, LeavesBattlefieldTriggeredEvent) for e in recorded))

    def test_death_fires_creature_dies(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('DyingCreature')
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert any((isinstance(e, CreatureDiesTriggeredEvent) for e in recorded))

    def test_death_fires_events_before_unregister(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('DyingCreature')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])
        death_trigger_fired = []

        def death_condition(game: Any, event: CreatureDiesTriggeredEvent) -> bool:
            return event.creature is creature

        def death_effect(game: Any) -> None:
            death_trigger_fired.append(True)
        trigger = TriggerRegistration(event_type=CreatureDiesTriggeredEvent, condition=death_condition, effect=death_effect, source=creature, controller=player)
        game.trigger_manager.register(trigger)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert not game.stack.is_empty() or len(death_trigger_fired) > 0
        assert len(game.trigger_manager.get_triggers_for_source(creature)) == 0

    def test_death_card_ends_in_graveyard(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('DyingCreature')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert player.zones[Zone.GRAVEYARD].contains(creature)
        assert not player.zones[Zone.BATTLEFIELD].contains(creature)

class TestMoveToZoneExile:
    """Exile a creature: battlefield to exile."""

    def test_exile_fires_leaves_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('ExiledCreature')
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.EXILE)
        assert any((isinstance(e, LeavesBattlefieldTriggeredEvent) for e in recorded))

    def test_exile_does_not_fire_creature_dies(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('ExiledCreature')
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.EXILE)
        assert not any((isinstance(e, CreatureDiesTriggeredEvent) for e in recorded))

    def test_exile_moves_to_exile_zone(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('ExiledCreature')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.EXILE)
        assert player.zones[Zone.EXILE].contains(creature)
        assert not player.zones[Zone.BATTLEFIELD].contains(creature)

class TestMoveToZoneReplacementRedirection:
    """Replacement effect redirects graveyard destination to exile."""

    def _make_repl_event(self, game: Any, creature: Any) -> CreatureDiesReplacementEvent:
        player = game.players[0]
        return CreatureDiesReplacementEvent(creature=creature, destination='graveyard', controller=player, owner=player)

    def test_replacement_redirects_to_exile(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('RedirectedCreature')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        def redirect_to_exile(game: Any, event: CreatureDiesReplacementEvent) -> CreatureDiesReplacementEvent:
            event.destination = 'exile'
            return event
        repl = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=creature, condition=None, replacement=redirect_to_exile, controller=player)
        game.replacement_manager.register(repl)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD, replacement_event=self._make_repl_event(game, creature))
        assert player.zones[Zone.EXILE].contains(creature)
        assert not player.zones[Zone.GRAVEYARD].contains(creature)

    def test_replacement_redirect_suppresses_creature_dies(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('RedirectedCreature')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        def redirect_to_exile(game: Any, event: CreatureDiesReplacementEvent) -> CreatureDiesReplacementEvent:
            event.destination = 'exile'
            return event
        repl = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=creature, condition=None, replacement=redirect_to_exile, controller=player)
        game.replacement_manager.register(repl)
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD, replacement_event=self._make_repl_event(game, creature))
        assert not any((isinstance(e, CreatureDiesTriggeredEvent) for e in recorded))

    def test_replacement_redirect_still_fires_leaves_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        creature = _make_creature('RedirectedCreature')
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        def redirect_to_exile(game: Any, event: CreatureDiesReplacementEvent) -> CreatureDiesReplacementEvent:
            event.destination = 'exile'
            return event
        repl = ReplacementEffect(event_type=CreatureDiesReplacementEvent, source=creature, condition=None, replacement=redirect_to_exile, controller=player)
        game.replacement_manager.register(repl)
        recorded = _record_events(game)
        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD, replacement_event=self._make_repl_event(game, creature))
        assert any((isinstance(e, LeavesBattlefieldTriggeredEvent) for e in recorded))

class TestMoveToZoneNonCreature:
    """Non-creature permanent leaving battlefield."""

    def test_enchantment_leaving_fires_leaves_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        enchantment = _make_enchantment('TestEnchantment')
        set_board_state(game, 0, battlefield=[enchantment])
        recorded = _record_events(game)
        move_to_zone(game, enchantment, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert any((isinstance(e, LeavesBattlefieldTriggeredEvent) for e in recorded))

    def test_enchantment_leaving_does_not_fire_creature_dies(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        enchantment = _make_enchantment('TestEnchantment')
        set_board_state(game, 0, battlefield=[enchantment])
        recorded = _record_events(game)
        move_to_zone(game, enchantment, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert not any((isinstance(e, CreatureDiesTriggeredEvent) for e in recorded))

class TestMoveToZoneToken:
    """Token creature going to graveyard."""

    def test_token_to_graveyard_fires_leaves_battlefield(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        token = _make_token_creature('SoldierToken')
        set_board_state(game, 0, battlefield=[token])
        recorded = _record_events(game)
        move_to_zone(game, token, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert any((isinstance(e, LeavesBattlefieldTriggeredEvent) for e in recorded))

    def test_token_to_graveyard_fires_creature_dies(self) -> None:
        from engine.zones import move_to_zone
        game = create_game()
        token = _make_token_creature('SoldierToken')
        set_board_state(game, 0, battlefield=[token])
        recorded = _record_events(game)
        move_to_zone(game, token, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        assert any((isinstance(e, CreatureDiesTriggeredEvent) for e in recorded))
