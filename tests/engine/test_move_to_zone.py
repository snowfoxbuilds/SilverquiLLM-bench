"""Tests for engine/zones.py — move_to_zone() centralized zone-transition hooks.

Verifies the high-level move_to_zone() function correctly:
- Removes card from source zone and adds to destination zone.
- Fires LEAVES_BATTLEFIELD and unregisters triggers when leaving battlefield.
- Fires ENTERS_BATTLEFIELD and registers triggers when entering battlefield.
- Fires CREATURE_DIES only for creatures going to graveyard.
- Consults replacement effects for zone-change redirection.
- Handles non-creature permanents and tokens appropriately.
"""

from __future__ import annotations

from typing import Any

import pytest

from engine.card import CardImpl, Creature, Enchantment
from engine.replacement_effects import ReplacementEffect
from engine.triggers import EventType, TriggerRegistration
from engine.types import CardType, Zone

from tests.test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creature(name: str = "TestCreature", power: int = 2, toughness: int = 2) -> Creature:
    """Create a simple creature for testing."""
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _make_enchantment(name: str = "TestEnchantment") -> Enchantment:
    """Create a simple enchantment for testing."""
    return Enchantment(name=name)


def _make_token_creature(name: str = "TokenCreature", power: int = 1, toughness: int = 1) -> Creature:
    """Create a token creature for testing."""
    token = Creature(name=name, base_power=power, base_toughness=toughness)
    token.is_token = True
    return token


class EventRecorder:
    """Records events fired by the trigger manager for test assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[EventType, dict[str, Any]]] = []

    def make_trigger(
        self,
        event_type: EventType,
        source: Any,
        controller: Any,
        *,
        condition: Any = None,
    ) -> TriggerRegistration:
        """Create a trigger registration that records when it fires."""
        recorder = self

        def effect(game: Any) -> None:
            pass  # StackObject on_resolve; actual recording happens via condition check

        return TriggerRegistration(
            event_type=event_type,
            condition=condition,
            effect=effect,
            source=source,
            controller=controller,
        )


def _record_events(game: Any) -> list[tuple[EventType, dict[str, Any]]]:
    """Monkey-patch the trigger manager to record all fired events.

    Returns the list that events are appended to.
    """
    original_fire = game.trigger_manager.fire_event.__func__
    recorded: list[tuple[EventType, dict[str, Any]]] = []

    def recording_fire(self: Any, game: Any, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        recorded.append((event_type, data or {}))
        original_fire(self, game, event_type, data)

    import types
    game.trigger_manager.fire_event = types.MethodType(recording_fire, game.trigger_manager)
    return recorded


# ---------------------------------------------------------------------------
# Tests: Bounce — battlefield to hand
# ---------------------------------------------------------------------------


class TestMoveToZoneBounce:
    """Bounce a creature from battlefield to hand."""

    def test_bounce_removes_from_battlefield_adds_to_hand(self) -> None:
        """move_to_zone should remove card from battlefield and add to hand."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("Bouncee")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)

        assert not player.zones[Zone.BATTLEFIELD].contains(creature)
        assert player.zones[Zone.HAND].contains(creature)

    def test_bounce_fires_leaves_battlefield(self) -> None:
        """Bouncing a creature should fire LEAVES_BATTLEFIELD event."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("Bouncee")
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)

        event_types = [et for et, _ in recorded]
        assert EventType.LEAVES_BATTLEFIELD in event_types

    def test_bounce_does_not_fire_creature_dies(self) -> None:
        """Bouncing to hand should NOT fire CREATURE_DIES."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("Bouncee")
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)

        event_types = [et for et, _ in recorded]
        assert EventType.CREATURE_DIES not in event_types

    def test_bounce_unregisters_triggers(self) -> None:
        """After bouncing, the creature's triggers should be unregistered."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("Bouncee")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        # Register a trigger for this creature
        trigger = TriggerRegistration(
            event_type=EventType.BEGINNING_OF_UPKEEP,
            condition=None,
            effect=lambda g: None,
            source=creature,
            controller=player,
        )
        game.trigger_manager.register(trigger)
        assert len(game.trigger_manager.get_triggers_for_source(creature)) == 1

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)

        # Trigger should be unregistered after leaving battlefield
        assert len(game.trigger_manager.get_triggers_for_source(creature)) == 0

    def test_bounce_unregisters_replacement_effects(self) -> None:
        """After bouncing, the creature's replacement effects should be unregistered."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("Bouncee")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        # Register a replacement effect for this creature
        repl = ReplacementEffect(
            event_type="creature_dies",
            source=creature,
            condition=None,
            replacement=lambda g, d: d,
            controller=player,
        )
        game.replacement_manager.register(repl)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.HAND)

        # Replacement effects should be unregistered after leaving battlefield
        remaining = [r for r in game.replacement_manager._effects if r.source is creature]
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# Tests: ETB — hand to battlefield
# ---------------------------------------------------------------------------


class TestMoveToZoneETB:
    """Enter the battlefield: hand to battlefield."""

    def test_etb_fires_enters_battlefield(self) -> None:
        """Moving from hand to battlefield should fire ENTERS_BATTLEFIELD."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("ETBCreature")
        set_board_state(game, 0, hand=[creature])
        recorded = _record_events(game)

        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)

        event_types = [et for et, _ in recorded]
        assert EventType.ENTERS_BATTLEFIELD in event_types

    def test_etb_calls_register_triggers(self) -> None:
        """Moving to battlefield should call register_triggers on the card."""
        from engine.zones import move_to_zone

        game = create_game()
        registered = []

        class TriggerCreature(Creature):
            def register_triggers(self, game: Any) -> None:
                registered.append(True)

        creature = TriggerCreature(name="TriggerBear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[creature])

        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)

        assert len(registered) == 1

    def test_etb_calls_register_replacement_effects(self) -> None:
        """Moving to battlefield should call register_replacement_effects on the card."""
        from engine.zones import move_to_zone

        game = create_game()
        registered = []

        class ReplCreature(Creature):
            def register_replacement_effects(self, game: Any) -> None:
                registered.append(True)

        creature = ReplCreature(name="ReplBear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[creature])

        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)

        assert len(registered) == 1

    def test_etb_adds_to_battlefield(self) -> None:
        """Card should end up on the battlefield after ETB move."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("ETBCreature")
        player = game.players[0]
        set_board_state(game, 0, hand=[creature])

        move_to_zone(game, creature, Zone.HAND, Zone.BATTLEFIELD)

        assert player.zones[Zone.BATTLEFIELD].contains(creature)
        assert not player.zones[Zone.HAND].contains(creature)


# ---------------------------------------------------------------------------
# Tests: Death — battlefield to graveyard (creature)
# ---------------------------------------------------------------------------


class TestMoveToZoneDeath:
    """Creature dying: battlefield to graveyard."""

    def test_death_fires_leaves_battlefield(self) -> None:
        """A creature going to graveyard should fire LEAVES_BATTLEFIELD."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("DyingCreature")
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        event_types = [et for et, _ in recorded]
        assert EventType.LEAVES_BATTLEFIELD in event_types

    def test_death_fires_creature_dies(self) -> None:
        """A creature going to graveyard should fire CREATURE_DIES."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("DyingCreature")
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        event_types = [et for et, _ in recorded]
        assert EventType.CREATURE_DIES in event_types

    def test_death_fires_events_before_unregister(self) -> None:
        """Events should fire BEFORE triggers are unregistered.

        This ensures self-referencing death triggers ("when this creature dies")
        can still match, per KEY_DECISIONS.
        """
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("DyingCreature")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        # Track when events fire relative to unregister
        death_trigger_fired = []

        def death_condition(game: Any, data: dict[str, Any]) -> bool:
            return data.get("creature") is creature

        def death_effect(game: Any) -> None:
            death_trigger_fired.append(True)

        trigger = TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=death_condition,
            effect=death_effect,
            source=creature,
            controller=player,
        )
        game.trigger_manager.register(trigger)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        # The trigger should have been pushed to the stack before unregister
        assert not game.stack.is_empty() or len(death_trigger_fired) > 0
        # After move_to_zone, the trigger should be unregistered
        assert len(game.trigger_manager.get_triggers_for_source(creature)) == 0

    def test_death_card_ends_in_graveyard(self) -> None:
        """After death, the creature should be in the graveyard."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("DyingCreature")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        assert player.zones[Zone.GRAVEYARD].contains(creature)
        assert not player.zones[Zone.BATTLEFIELD].contains(creature)


# ---------------------------------------------------------------------------
# Tests: Exile — battlefield to exile
# ---------------------------------------------------------------------------


class TestMoveToZoneExile:
    """Exile a creature: battlefield to exile."""

    def test_exile_fires_leaves_battlefield(self) -> None:
        """Exiling should fire LEAVES_BATTLEFIELD."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("ExiledCreature")
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.EXILE)

        event_types = [et for et, _ in recorded]
        assert EventType.LEAVES_BATTLEFIELD in event_types

    def test_exile_does_not_fire_creature_dies(self) -> None:
        """Exiling a creature should NOT fire CREATURE_DIES (only graveyard counts as death)."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("ExiledCreature")
        set_board_state(game, 0, battlefield=[creature])
        recorded = _record_events(game)

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.EXILE)

        event_types = [et for et, _ in recorded]
        assert EventType.CREATURE_DIES not in event_types

    def test_exile_moves_to_exile_zone(self) -> None:
        """Exiled creature should end up in the exile zone."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("ExiledCreature")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.EXILE)

        assert player.zones[Zone.EXILE].contains(creature)
        assert not player.zones[Zone.BATTLEFIELD].contains(creature)


# ---------------------------------------------------------------------------
# Tests: Replacement effect — zone-change redirection
# ---------------------------------------------------------------------------


class TestMoveToZoneReplacementRedirection:
    """Replacement effect redirects graveyard destination to exile."""

    def test_replacement_redirects_to_exile(self) -> None:
        """A replacement effect should redirect graveyard to exile."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("RedirectedCreature")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        # Register a replacement effect that redirects graveyard→exile
        def redirect_to_exile(game: Any, event_data: dict[str, Any]) -> dict[str, Any]:
            event_data["destination"] = "exile"
            return event_data

        repl = ReplacementEffect(
            event_type="creature_dies",
            source=creature,
            condition=None,
            replacement=redirect_to_exile,
            controller=player,
        )
        game.replacement_manager.register(repl)

        move_to_zone(
            game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD,
            replacement_event_type="creature_dies",
        )

        # Creature should be in exile, not graveyard
        assert player.zones[Zone.EXILE].contains(creature)
        assert not player.zones[Zone.GRAVEYARD].contains(creature)

    def test_replacement_redirect_suppresses_creature_dies(self) -> None:
        """When redirected from graveyard to exile, CREATURE_DIES should NOT fire.

        Per KEY_DECISIONS: a creature only "dies" if it reaches the graveyard.
        """
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("RedirectedCreature")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        def redirect_to_exile(game: Any, event_data: dict[str, Any]) -> dict[str, Any]:
            event_data["destination"] = "exile"
            return event_data

        repl = ReplacementEffect(
            event_type="creature_dies",
            source=creature,
            condition=None,
            replacement=redirect_to_exile,
            controller=player,
        )
        game.replacement_manager.register(repl)
        recorded = _record_events(game)

        move_to_zone(
            game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD,
            replacement_event_type="creature_dies",
        )

        event_types = [et for et, _ in recorded]
        assert EventType.CREATURE_DIES not in event_types

    def test_replacement_redirect_still_fires_leaves_battlefield(self) -> None:
        """Even when redirected, LEAVES_BATTLEFIELD should still fire."""
        from engine.zones import move_to_zone

        game = create_game()
        creature = _make_creature("RedirectedCreature")
        player = game.players[0]
        set_board_state(game, 0, battlefield=[creature])

        def redirect_to_exile(game: Any, event_data: dict[str, Any]) -> dict[str, Any]:
            event_data["destination"] = "exile"
            return event_data

        repl = ReplacementEffect(
            event_type="creature_dies",
            source=creature,
            condition=None,
            replacement=redirect_to_exile,
            controller=player,
        )
        game.replacement_manager.register(repl)
        recorded = _record_events(game)

        move_to_zone(
            game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD,
            replacement_event_type="creature_dies",
        )

        event_types = [et for et, _ in recorded]
        assert EventType.LEAVES_BATTLEFIELD in event_types


# ---------------------------------------------------------------------------
# Tests: Non-creature permanent (enchantment)
# ---------------------------------------------------------------------------


class TestMoveToZoneNonCreature:
    """Non-creature permanent leaving battlefield."""

    def test_enchantment_leaving_fires_leaves_battlefield(self) -> None:
        """An enchantment leaving battlefield should fire LEAVES_BATTLEFIELD."""
        from engine.zones import move_to_zone

        game = create_game()
        enchantment = _make_enchantment("TestEnchantment")
        set_board_state(game, 0, battlefield=[enchantment])
        recorded = _record_events(game)

        move_to_zone(game, enchantment, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        event_types = [et for et, _ in recorded]
        assert EventType.LEAVES_BATTLEFIELD in event_types

    def test_enchantment_leaving_does_not_fire_creature_dies(self) -> None:
        """A non-creature permanent should NOT fire CREATURE_DIES."""
        from engine.zones import move_to_zone

        game = create_game()
        enchantment = _make_enchantment("TestEnchantment")
        set_board_state(game, 0, battlefield=[enchantment])
        recorded = _record_events(game)

        move_to_zone(game, enchantment, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        event_types = [et for et, _ in recorded]
        assert EventType.CREATURE_DIES not in event_types


# ---------------------------------------------------------------------------
# Tests: Token creature
# ---------------------------------------------------------------------------


class TestMoveToZoneToken:
    """Token creature going to graveyard."""

    def test_token_to_graveyard_fires_leaves_battlefield(self) -> None:
        """A token going to graveyard should fire LEAVES_BATTLEFIELD."""
        from engine.zones import move_to_zone

        game = create_game()
        token = _make_token_creature("SoldierToken")
        set_board_state(game, 0, battlefield=[token])
        recorded = _record_events(game)

        move_to_zone(game, token, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        event_types = [et for et, _ in recorded]
        assert EventType.LEAVES_BATTLEFIELD in event_types

    def test_token_to_graveyard_fires_creature_dies(self) -> None:
        """A token creature going to graveyard should fire CREATURE_DIES.

        Tokens do go to the graveyard momentarily before being cleaned up
        by SBAs, so death triggers should fire.
        """
        from engine.zones import move_to_zone

        game = create_game()
        token = _make_token_creature("SoldierToken")
        set_board_state(game, 0, battlefield=[token])
        recorded = _record_events(game)

        move_to_zone(game, token, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        event_types = [et for et, _ in recorded]
        assert EventType.CREATURE_DIES in event_types
