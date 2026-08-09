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

import inspect

from engine.events import TriggeredEvent
from engine.stack import StackObject, capture_activation_context

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _effect_wants_controller(effect: Callable[..., Any]) -> bool:
    """Return ``True`` if an *untargeted* trigger effect accepts the fire-time
    controller as a second positional argument — ``effect(game, controller)``.

    Controller-*insensitive* effects keep the historical ``effect(game)``
    signature and return ``False`` (they are invoked with the game alone). A
    controller-*sensitive* untargeted effect ("copy it for the controller",
    "that player draws") declares a second required positional parameter and is
    threaded the immutable fire-time controller, so it never re-reads
    ``source.controller`` at resolution. Every pre-existing untargeted effect is
    one-argument, so this is backward-compatible.
    """
    try:
        params = list(inspect.signature(effect).parameters.values())
    except (TypeError, ValueError):
        return False
    required = [
        p
        for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        and p.default is p.empty
    ]
    return len(required) >= 2


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
        effect: Callable executed when the trigger resolves (becomes the
            :attr:`StackObject.on_resolve` callback). For a *targeted* trigger
            (``targeting`` set) it is invoked ``effect(game, targets, context)`` —
            the targets chosen as the trigger was put on the stack and the
            :class:`~engine.stack.ActivationContext` captured then. For an
            *untargeted* trigger it is invoked ``effect(game)`` by default, or
            ``effect(game, controller)`` when it declares a second positional
            parameter — a *controller-sensitive* effect ("copy it for the
            controller") is threaded the immutable **fire-time** controller so it
            never re-reads ``source.controller`` at resolution.
        source: The game object (card / permanent) that owns this trigger.
        controller: The player who controls the source at the time of
            registration. Note the *fire-time* controller (the source's current
            controller when the trigger goes on the stack) is what the pipeline
            actually uses for grouping, the stack object, targeting, and the
            context (rule 603.3d/3e); this field is only the fallback for a source
            that no longer has a controller.
        targeting: Optional callable ``(game, event, controller) -> list | None``
            run **as the trigger is put on the stack** (rule 603.3d — a triggered
            ability chooses its targets when it goes on the stack, not when it
            resolves). *controller* is the trigger's controller **determined at
            fire time** (the current controller of :attr:`source`, falling back to
            :attr:`controller` — rule 603.3e), so a source whose control changed
            after registration targets and resolves relative to its *new*
            controller. Return value:

            * a **list** (possibly empty, for an "up to N target" trigger with
              none chosen) — the trigger is put on the stack with those targets;
            * ``None`` — a **required** target has no legal choice, so the
              trigger is **not put on the stack at all** (rule 603.3c). Use the
              empty-list return for the genuinely-optional "up to N" case; reserve
              ``None`` for required targets.

            The chosen targets and a fire-time
            :class:`~engine.stack.ActivationContext` (with the fire-time
            *controller*) are stored on the :class:`~engine.stack.StackObject` and
            passed to ``effect`` at resolution — targets are never re-selected.
    """

    event_type: type[TriggeredEvent]
    condition: Callable[..., bool] | None
    effect: Callable[..., None]
    source: Any
    controller: Player
    targeting: Callable[..., Any] | None = None


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

        # The controller of each triggered ability is determined when it is put
        # on the stack (rule 603.3d/3e): the source's *current* controller, or
        # the registration-time controller if the source no longer has one (e.g.
        # a leaves-the-battlefield trigger whose source is already gone). This
        # fire-time controller is used **consistently** across the whole
        # pipeline — APNAP grouping, the stack object (targeted *and* untargeted),
        # target selection, and the ActivationContext — so a source that changed
        # hands after registration triggers, orders, and resolves under its new
        # controller.
        def _fire_controller(trigger: TriggerRegistration) -> Any:
            return getattr(trigger.source, "controller", None) or trigger.controller

        active_player = game.active_player
        matched = [(trigger, _fire_controller(trigger)) for trigger in matching]
        active_triggers = [(t, c) for (t, c) in matched if c is active_player]
        non_active_triggers = [(t, c) for (t, c) in matched if c is not active_player]
        ordered = active_triggers + non_active_triggers

        for trigger, fire_controller in ordered:
            if trigger.targeting is not None:
                # Choose targets as the trigger goes on the stack.
                chosen = trigger.targeting(game, event, fire_controller)
                if chosen is None:
                    # A required target with no legal choice — the trigger is not
                    # put on the stack at all (rule 603.3c).
                    continue
                chosen_targets = list(chosen)
                context = capture_activation_context(
                    game, trigger.source, fire_controller, chosen_targets
                )
                stack_obj = StackObject(
                    source=trigger.source,
                    controller=fire_controller,
                    targets=chosen_targets,
                    activation_context=context,
                )
                effect = trigger.effect
                stack_obj.on_resolve = (
                    lambda g, _obj=stack_obj, _effect=effect: _effect(
                        g, _obj.targets, _obj.activation_context
                    )
                )
            else:
                effect = trigger.effect
                if _effect_wants_controller(effect):
                    # Thread the immutable fire-time controller into a
                    # controller-sensitive untargeted effect (effect(game,
                    # controller)); capture the context for consistency so the
                    # stack object reflects the same fire-time controller.
                    context = capture_activation_context(
                        game, trigger.source, fire_controller, []
                    )
                    stack_obj = StackObject(
                        source=trigger.source,
                        controller=fire_controller,
                        activation_context=context,
                    )
                    stack_obj.on_resolve = (
                        lambda g, _c=fire_controller, _e=effect: _e(g, _c)
                    )
                else:
                    stack_obj = StackObject(
                        source=trigger.source,
                        controller=fire_controller,
                        on_resolve=effect,
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
