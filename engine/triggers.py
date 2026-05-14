"""Triggered abilities system — event-driven trigger registration and firing.

Provides the core mechanism for registering triggered abilities and firing
events that push matching triggers onto the stack:

- :class:`EventType` — enumeration of game events that can trigger abilities.
- :class:`TriggerRegistration` — dataclass describing a single trigger.
- :class:`TriggerManager` — central registry for triggers with APNAP-ordered
  event firing.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from engine.stack import StackObject

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class EventType(enum.Enum):
    """Game events that can trigger abilities."""

    ENTERS_BATTLEFIELD = "enters_battlefield"
    LEAVES_BATTLEFIELD = "leaves_battlefield"
    DEALS_DAMAGE = "deals_damage"
    LOSES_LIFE = "loses_life"
    GAINS_LIFE = "gains_life"
    DRAWS_CARD = "draws_card"
    BEGINNING_OF_UPKEEP = "beginning_of_upkeep"
    BEGINNING_OF_COMBAT = "beginning_of_combat"
    END_OF_TURN = "end_of_turn"
    END_STEP = "end_step"
    CREATURE_DIES = "creature_dies"
    SPELL_CAST = "spell_cast"
    ATTACKS = "attacks"
    BLOCKS = "blocks"


@dataclass
class TriggerRegistration:
    """Describes a single triggered ability.

    Attributes:
        event_type: The event type that fires this trigger.
        condition: Optional callable ``(game, data) -> bool`` that must
            return ``True`` for the trigger to fire.  ``None`` means the
            trigger always fires for its event type.
        effect: Callable ``(game) -> None`` executed when the trigger
            resolves (becomes the :attr:`StackObject.on_resolve` callback).
        source: The game object (card / permanent) that owns this trigger.
        controller: The player who controls the source at the time of
            registration.
    """

    event_type: EventType
    condition: Callable[..., bool] | None
    effect: Callable[..., None]
    source: Any
    controller: Player


class TriggerManager:
    """Central registry for triggered abilities.

    Triggers are registered when a permanent enters the battlefield (or
    via other game actions) and unregistered when the source leaves.

    :meth:`fire_event` checks all registered triggers of a matching
    event type, evaluates their conditions, and pushes matching triggers
    onto the game stack as :class:`StackObject` instances.  Triggers are
    ordered according to APNAP (Active Player, Non-Active Player):

    * Active player's triggers are pushed first (end up on the bottom
      of the batch).
    * Non-active player's triggers are pushed second (end up on top).
    * Within the same player, triggers are pushed in registration order
      (controller would normally choose; for now we use registration
      order as a deterministic default).
    """

    def __init__(self) -> None:
        self._triggers: list[TriggerRegistration] = []

    def register(self, trigger: TriggerRegistration) -> None:
        """Register a triggered ability.

        Parameters:
            trigger: The :class:`TriggerRegistration` to add.
        """
        self._triggers.append(trigger)

    def unregister(self, source: Any) -> None:
        """Remove all triggers registered by *source* (identity-based).

        Called when a permanent leaves the battlefield.

        Parameters:
            source: The game object whose triggers should be removed.
        """
        self._triggers = [t for t in self._triggers if t.source is not source]

    def fire_event(
        self,
        game: GameState,
        event_type: EventType,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Fire an event and push all matching triggers onto the stack.

        Parameters:
            game: The current game state.
            event_type: The event that occurred.
            data: Optional dictionary of event-specific data passed to
                each trigger's condition callable.

        Matching triggers are pushed in APNAP order:

        1. Active player's matching triggers (in registration order).
        2. Non-active player's matching triggers (in registration order).
        """
        if data is None:
            data = {}

        # Collect matching triggers
        matching: list[TriggerRegistration] = []
        for trigger in self._triggers:
            if trigger.event_type != event_type:
                continue
            # Evaluate condition if present
            if trigger.condition is not None:
                if not trigger.condition(game, data):
                    continue
            matching.append(trigger)

        if not matching:
            return

        # Partition by controller into APNAP order
        active_player = game.active_player
        active_triggers: list[TriggerRegistration] = []
        non_active_triggers: list[TriggerRegistration] = []

        for trigger in matching:
            if trigger.controller is active_player:
                active_triggers.append(trigger)
            else:
                non_active_triggers.append(trigger)

        # Push active player's triggers first (they end up on the bottom),
        # then non-active player's triggers (they end up on top).
        ordered = active_triggers + non_active_triggers

        for trigger in ordered:
            stack_obj = StackObject(
                source=trigger.source,
                controller=trigger.controller,
                on_resolve=trigger.effect,
            )
            game.stack.push(stack_obj)

    def get_triggers(self) -> list[TriggerRegistration]:
        """Return a shallow copy of all registered triggers.

        Useful for inspection and testing.
        """
        return list(self._triggers)

    def get_triggers_for_source(self, source: Any) -> list[TriggerRegistration]:
        """Return all triggers registered by *source* (identity-based).

        Parameters:
            source: The game object to filter by.
        """
        return [t for t in self._triggers if t.source is source]

    def clear(self) -> None:
        """Remove all registered triggers."""
        self._triggers.clear()
