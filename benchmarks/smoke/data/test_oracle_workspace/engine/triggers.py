"""Triggered abilities system — event-driven trigger registration and firing.

Provides the core mechanism for registering triggered abilities and firing
events that push matching triggers onto the stack:

- :class:`TriggerRegistration` — dataclass describing a single trigger.
- :class:`TriggerManager` — central registry for triggers with APNAP-ordered
  event firing.

Event types live in :mod:`engine.events` as typed dataclasses.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Callable, Iterator, NamedTuple

import inspect

from engine.events import TriggeredEvent
from engine.stack import StackObject, battlefield_stint_id, capture_activation_context

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _required_positional(effect: Callable[..., Any]) -> int:
    """The number of required positional parameters *effect* declares."""
    try:
        params = list(inspect.signature(effect).parameters.values())
    except (TypeError, ValueError):
        return 1
    return len([
        p
        for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        and p.default is p.empty
    ])


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
            *untargeted* trigger with a ``capture`` hook it is invoked
            ``effect(game, controller, event_state)`` — the immutable fire-time
            controller and the per-fire state ``capture`` returned. For a plain
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
        capture: Optional callable ``(game, event, controller) -> Any`` run **as
            the ability triggers** (rule 603.2 — a trigger's event-specific
            facts are fixed then, not when it goes on the stack or resolves). *controller*
            is the same fire-time controller ``targeting`` receives. Its return
            value — arbitrary immutable per-fire state — is stored on the
            :class:`~engine.stack.StackObject` as
            :attr:`~engine.stack.StackObject.event_state` and passed to ``effect``
            as ``effect(game, controller, event_state)`` at resolution. This is
            how a trigger correlates itself to *this* firing's facts (Thousand-Year
            Storm captures the triggering spell's ``StackObject`` and its copy
            count) **without** a mutable source-level slot that later firings would
            clobber. ``capture`` is for *untargeted* triggers (a targeted trigger
            uses ``targeting`` + the effect's ``targets``/``context`` instead).
        printed: The predefined class of the printed ability this trigger
            comes from (see ADR-017); its stack objects carry it.
    """

    event_type: type[TriggeredEvent]
    condition: Callable[..., bool] | None
    effect: Callable[..., None]
    source: Any
    controller: Player
    targeting: Callable[..., Any] | None = None
    capture: Callable[..., Any] | None = None
    printed: type | None = None


class TriggerManager:
    """Central registry for triggered abilities.

    Triggers are registered when a permanent enters the battlefield (or
    via other game actions) and unregistered when the source leaves.

    :meth:`fire_event` checks all registered triggers of a matching
    event type and evaluates their conditions; each triggered occurrence,
    with its event and fire-time controller, waits until the game next
    settles before a player would receive priority (rule 117.5, 603.3), when
    :meth:`put_pending_on_stack` puts every waiting occurrence on the stack
    as :class:`StackObject` instances, in APNAP order (rule 603.3b):

    * The active player orders all of theirs, through an ordering Player
      Query when there are two or more, and puts them on the stack —
      choosing each one's targets — before the non-active player is asked.
    * The non-active player's then go on top of them the same way.
    """

    def __init__(self) -> None:
        self._triggers: list[TriggerRegistration] = []
        self._batch_depth = 0
        self._pending: list[_Occurrence] = []

    @contextmanager
    def batch(self, game: GameState) -> Iterator[None]:
        """Settle the game when the block ends, for a caller that drives
        events outside the step lifecycle (a declaration or a combat damage
        pass run directly): it reaches the same boundary the game settles at
        before a player would receive priority
        (:func:`~engine.state_based_actions.resolve_state_based_actions`), so
        every ability that triggered in the block goes on the stack together
        (rule 117.5, 603.3b). Nested blocks settle at the outermost; a block
        left by an exception leaves the waiting abilities to the enclosing
        rollback."""
        self._batch_depth += 1
        try:
            yield
        finally:
            self._batch_depth -= 1
        if self._batch_depth == 0:
            from engine.state_based_actions import resolve_state_based_actions

            resolve_state_based_actions(game)

    def register(self, trigger: TriggerRegistration) -> None:
        """Register a triggered ability."""
        self._triggers.append(trigger)

    def unregister(self, source: Any) -> None:
        """Remove all triggers registered by *source* (identity-based)."""
        self._triggers = [t for t in self._triggers if t.source is not source]

    def fire_event(self, game: GameState, event: TriggeredEvent) -> None:
        """Fire an event: every matching trigger's occurrence waits, with the
        facts fixed as it triggers, until :meth:`put_pending_on_stack` puts it
        on the stack when the game next settles.

        Parameters:
            game: The current game state.
            event: The typed event object.  Triggers registered for the
                event's class or any of its parent classes will fire.
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
        # A leaves-the-battlefield ability's source is already a new object
        # (rule 400.7), so its controller is read as it last existed (603.10a).
        last_known = getattr(event, "last_known", None)

        def _fire_controller(trigger: TriggerRegistration) -> Any:
            if last_known is not None and last_known.card is trigger.source:
                return last_known.controller or trigger.controller
            return getattr(trigger.source, "controller", None) or trigger.controller

        for trigger in matching:
            controller = _fire_controller(trigger)
            # An occurrence's event facts are fixed when it triggers (rule 603.2,
            # 603.10a), even though it goes on the stack only when the game settles.
            state = trigger.capture(game, event, controller) if trigger.capture is not None else None
            # So is its source's identity: a source that leaves and returns before
            # the occurrence is placed is a new object (rule 400.7), so the
            # occurrence keeps the stint its source had when it triggered.
            self._pending.append(
                _Occurrence(
                    trigger=trigger,
                    controller=controller,
                    event=event,
                    captured=state,
                    source_stint=battlefield_stint_id(game, trigger.source),
                    source_instance=game.refs.instance_id(trigger.source, _zone_of(game, trigger.source)),
                )
            )

    def has_pending(self) -> bool:
        """Whether triggered abilities are waiting to be put on the stack."""
        return bool(self._pending)

    def discard_pending(self) -> None:
        """Drop every waiting occurrence: the game ended before they could be
        put on the stack (rule 104.1)."""
        self._pending = []

    def put_pending_on_stack(self, game: GameState) -> bool:
        """Put every triggered ability waiting since a player last received
        priority on the stack, and return whether there were any (rule
        117.5, 603.3b).

        Each player in APNAP order, starting with the active player, chooses
        the order of all of their own and puts them on the stack, choosing
        targets as each goes on, before the next player is asked. One
        player's placement is an attempt (:func:`engine.attempts.attempt`):
        a rejected choice rolls back only that player's placement, waiting
        occurrences included, and asks again. An ability that triggers while
        these are placed waits for the next settling iteration.
        """
        if game.is_game_over:
            self.discard_pending()
            return False
        if not self._pending:
            return False
        from engine import attempts

        pending, self._pending = self._pending, []
        for player in _apnap(game):
            group = [m for m in pending if m.controller is player]
            if group:
                attempts.attempt(game, lambda group=group: self._place(game, _chosen_order(game, group)))
        others = [m for m in pending if all(m.controller is not p for p in _apnap(game))]
        if others:
            self._place(game, others)
        return True

    def _place(self, game: GameState, ordered: list[_Occurrence]) -> None:
        """Put one player's triggered abilities on the stack in *ordered*
        order, the first at the bottom. Targets are chosen, and their stints
        captured, now; each source's stint is the one it had when it
        triggered."""
        for occurrence in ordered:
            trigger, fire_controller, event, captured = occurrence[:4]
            if trigger.targeting is not None:
                # Choose targets as the trigger goes on the stack.
                chosen = trigger.targeting(game, event, fire_controller)
                if chosen is None:
                    # A required target with no legal choice — the trigger is not
                    # put on the stack at all (rule 603.3c).
                    continue
                chosen_targets = list(chosen)
                context = _occurrence_context(game, occurrence, chosen_targets)
                stack_obj = StackObject(
                    source=trigger.source,
                    controller=fire_controller,
                    printed=trigger.printed,
                    targets=chosen_targets,
                    activation_context=context,
                )
                effect = trigger.effect
                stack_obj.on_resolve = (
                    lambda g, _obj=stack_obj, _effect=effect: _effect(
                        g, _obj.targets, _obj.activation_context
                    )
                )
                game.stack.push(stack_obj)
            elif trigger.capture is not None:
                # Untargeted trigger that captured per-fire event state when it
                # triggered (rule 603.3), stored on this trigger's own
                # StackObject, so two pending triggers of the same source hold
                # independent state. The effect reads the immutable fire-time
                # controller and that state — never a mutable source-level slot.
                event_state = captured
                context = _occurrence_context(game, occurrence, [])
                stack_obj = StackObject(
                    source=trigger.source,
                    controller=fire_controller,
                    printed=trigger.printed,
                    activation_context=context,
                    event_state=event_state,
                )
                effect = trigger.effect
                stack_obj.on_resolve = (
                    lambda g, _c=fire_controller, _e=effect, _s=event_state: _e(
                        g, _c, _s
                    )
                )
                game.stack.push(stack_obj)
            else:
                effect = trigger.effect
                if _effect_wants_controller(effect):
                    # Thread the immutable fire-time controller into a
                    # controller-sensitive untargeted effect (effect(game,
                    # controller)); capture the context for consistency so the
                    # stack object reflects the same fire-time controller.
                    context = _occurrence_context(game, occurrence, [])
                    stack_obj = StackObject(
                        source=trigger.source,
                        controller=fire_controller,
                        printed=trigger.printed,
                        activation_context=context,
                    )
                    stack_obj.on_resolve = (
                        lambda g, _c=fire_controller, _e=effect: _e(g, _c)
                    )
                else:
                    stack_obj = StackObject(
                        source=trigger.source,
                        controller=fire_controller,
                        printed=trigger.printed,
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


def register_delayed_trigger(
    game: GameState,
    event_type: type[TriggeredEvent],
    controller: Player,
    effect: Callable[..., None],
    *,
    condition: Callable[..., bool] | None = None,
    name: str = "Delayed trigger",
    printed: type | None = None,
) -> None:
    """Create a delayed triggered ability (rule 603.7).

    It triggers only once, the next time an *event_type* event satisfies
    *condition* (603.7b), and is controlled by *controller* (603.7d-e). It is
    registered under a marker object of its own, so it survives the creating
    object leaving the battlefield. *effect* follows the untargeted
    :class:`TriggerRegistration`
    contract: ``effect(game)`` or ``effect(game, controller)``. *printed* is
    the predefined class of the printed ability that creates it.
    """
    from engine.card import CardImpl

    marker = CardImpl(name=name, owner=controller)

    def _once(game: GameState, event: TriggeredEvent) -> bool:
        if condition is not None and not condition(game, event):
            return False
        game.trigger_manager.unregister(marker)
        return True

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=event_type,
            condition=_once,
            effect=effect,
            source=marker,
            controller=controller,
            printed=printed,
        )
    )


class _Occurrence(NamedTuple):
    """One triggered ability waiting to be put on the stack, with the facts
    fixed when it triggered: its fire-time controller, event and captured
    state, and its source's battlefield stint and instance id then
    (rule 400.7, 603.2)."""

    trigger: TriggerRegistration
    controller: Any
    event: TriggeredEvent
    captured: Any
    source_stint: int | None
    source_instance: int


def _occurrence_context(game: GameState, occurrence: _Occurrence, targets: list[Any]) -> Any:
    """The activation context of *occurrence* as it goes on the stack: its
    targets' stints as chosen now, its source's stint as it triggered."""
    context = capture_activation_context(game, occurrence.trigger.source, occurrence.controller, targets)
    return replace(context, source_instance_id=occurrence.source_stint)


def _apnap(game: GameState) -> list[Any]:
    """The players in APNAP order: the active player, then the others in turn
    order (rule 101.4)."""
    players = list(game.players)
    start = next((i for i, p in enumerate(players) if p is game.active_player), 0)
    return players[start:] + players[:start]


def _chosen_order(game: GameState, group: list[_Occurrence]) -> list[_Occurrence]:
    """*group* — one player's triggered abilities that triggered together — in
    the order its controller puts them on the stack (rule 603.3b).

    Two or more are an ordering Player Query to their controller: an ABILITY
    option per triggered ability, naming its printed ability class, its
    source's instance and its place among that source's abilities in the
    group, every option to be chosen,
    and the first chosen is put on the stack first. Registration order is the
    offered order.
    """
    if len(group) < 2:
        return group
    from engine.decisions import Decision, GameRef
    from engine.queries import PlayerQuery, ask

    controller = group[0].controller
    seat = game.refs.seat_of(controller)
    by_decision: dict[Any, _Occurrence] = {}
    ordinals: dict[int, int] = {}
    for item in group:
        source, printed = item.trigger.source, item.trigger.printed
        ordinal = ordinals[id(source)] = ordinals.get(id(source), -1) + 1
        instance = item.source_instance
        attrs: dict[str, Any] = {"source": instance, "index": ordinal}
        if printed is not None:
            attrs["printed"] = printed
        decision = Decision.ability(
            ref=GameRef(object=frozenset({("instance", instance)}), ability=frozenset({("index", ordinal)})),
            **attrs,
        )
        by_decision[decision] = item
    query = PlayerQuery(
        source=(game.refs.player_decision(controller, seat=seat),),
        prompt="order your triggered abilities: the first chosen is put on the stack first",
        options=tuple(by_decision),
        min=len(by_decision),
        max=len(by_decision),
    )
    return [by_decision[d] for d in ask(controller, query).selected]


def _zone_of(game: GameState, obj: Any) -> str:
    """The zone *obj* is in — the stack when it is in no player's zone."""
    from engine.types import Zone

    for player in game.players:
        for zone in Zone:
            if zone in player.zones and player.zones[zone].contains(obj):
                return zone.value
    return "stack"
