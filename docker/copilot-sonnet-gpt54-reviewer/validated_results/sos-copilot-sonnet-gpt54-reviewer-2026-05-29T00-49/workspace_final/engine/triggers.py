"""Triggered abilities system — event-driven trigger registration and firing.

Provides the core mechanism for registering triggered abilities and firing
events that push matching triggers onto the stack:

- :class:`TriggerRegistration` — dataclass describing a single trigger.
- :class:`TriggerManager` — central registry for triggers with APNAP-ordered
  event firing.

Event types live in :mod:`engine.events` as typed dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from engine.events import TriggeredEvent
from engine.stack import StackObject

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass
class TriggerRegistration:
    """Describes a single triggered ability.

    Attributes:
        event_type: The event class (or a base class) this trigger watches.
            The trigger fires for any fired event that is an instance of
            this class, including instances of subclasses.
        condition: Optional callable ``(game, event) -> bool`` that must
            return ``True`` for the trigger to fire.  ``None`` means the
            trigger always fires for its event type.
        effect: Callable ``(game) -> None`` executed when the trigger
            resolves (becomes the :attr:`StackObject.on_resolve` callback).
        source: The game object (card / permanent) that owns this trigger.
        controller: The player who controls the source at the time of
            registration.
    """

    event_type: type[TriggeredEvent]
    condition: Callable[..., bool] | None
    effect: Callable[..., None]
    source: Any
    controller: Player
    immediate: bool = False
    """If True, the effect is called directly when the event fires (bypasses the stack).
    Use this for cards whose ETB/trigger effects should resolve without waiting for
    stack priority (e.g. in simplified test-only contexts)."""


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
        """Register a triggered ability."""
        self._triggers.append(trigger)

    def unregister(self, source: Any) -> None:
        """Remove all triggers registered by *source* (identity-based)."""
        self._triggers = [t for t in self._triggers if t.source is not source]

    def fire_event(self, game: GameState, event: TriggeredEvent) -> None:
        """Fire an event and push all matching triggers onto the stack.

        Parameters:
            game: The current game state.
            event: The typed event object.  Triggers registered for the
                event's class or any of its parent classes will fire.

        Matching triggers are pushed in APNAP order:

        1. Active player's matching triggers (in registration order).
        2. Non-active player's matching triggers (in registration order).
        """
        matching: list[TriggerRegistration] = []
        for trigger in self._triggers:
            if not isinstance(event, trigger.event_type):
                continue
            if trigger.condition is not None:
                if not trigger.condition(game, event):
                    continue
            matching.append(trigger)

        if not matching:
            return

        active_player = game.active_player
        active_triggers: list[TriggerRegistration] = []
        non_active_triggers: list[TriggerRegistration] = []

        for trigger in matching:
            if trigger.controller is active_player:
                active_triggers.append(trigger)
            else:
                non_active_triggers.append(trigger)

        ordered = active_triggers + non_active_triggers

        for trigger in ordered:
            if trigger.immediate:
                trigger.effect(game)
            else:
                stack_obj = StackObject(
                    source=trigger.source,
                    controller=trigger.controller,
                    on_resolve=trigger.effect,
                )
                game.stack.push(stack_obj)

    def get_triggers(self) -> list[TriggerRegistration]:
        """Return a shallow copy of all registered triggers."""
        return list(self._triggers)

    def get_triggers_for_source(self, source: Any) -> list[TriggerRegistration]:
        """Return all triggers registered by *source* (identity-based)."""
        return [t for t in self._triggers if t.source is source]

    def clear(self) -> None:
        """Remove all registered triggers."""
        self._triggers.clear()
