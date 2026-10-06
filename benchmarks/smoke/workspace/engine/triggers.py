"""Triggered abilities system — event-driven trigger registration and firing.

Provides the core mechanism for registering triggered abilities and firing
events that push matching triggers onto the stack:

- :class:`TriggerRegistration` — dataclass describing a single trigger.
- :class:`TriggerManager` — central registry for triggers with APNAP-ordered
  event firing.

Event types live in :mod:`engine.events` as typed dataclasses.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable, Iterator, NamedTuple

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
            clobber. On a targeted trigger it runs right after ``targeting``, and
            ``effect`` is called ``effect(game, targets, context, event_state)``.
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
            # A targeted trigger captures right after choosing its targets
            # instead, since what it keeps may depend on them.
            fire_time = trigger.capture is not None and trigger.targeting is None
            state = trigger.capture(game, event, controller) if fire_time else None
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
                if trigger.capture is not None:
                    stack_obj.event_state = trigger.capture(game, event, fire_controller)
                    stack_obj.on_resolve = (
                        lambda g, _obj=stack_obj, _effect=effect: _effect(
                            g, _obj.targets, _obj.activation_context, _obj.event_state
                        )
                    )
                else:
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


def choose_trigger_targets(
    game: GameState, controller: Player, source: Any, requirements: list[Any]
) -> list[Any] | None:
    """Choose a triggered ability's targets as it is put on the stack (rule
    603.3d): one Player Query per target requirement, asked of the ability's
    *controller*, each target distinct from those already chosen.

    Returns ``None`` when a required target has no legal choice, so the
    ability is removed from the stack (rule 603.3c); a declined or
    unavailable optional ("up to one") target is simply left out.
    """
    from engine.casting import CastingError, _query_target

    chosen: list[Any] = []
    for requirement in requirements:
        try:
            target = _query_target(game, controller, source, requirement, exclude=chosen, protect_from=source)
        except CastingError:
            return None
        if target is not None:
            chosen.append(target)
    return chosen


def still_legal_targets(game: GameState, source: Any, requirements: list[Any], targets: list[Any]) -> list[Any]:
    """*targets* with each one no longer legal on resolution replaced by
    ``None`` (rule 608.2b): it must still be in its requirement's zone, satisfy
    the requirement's whole predicate — the one built for the ability's
    controller when it was put on the stack — and not have protection from
    *source*. Targets are never re-chosen. An optional requirement left
    unchosen is skipped, so each target is checked against the next
    requirement it can belong to."""
    from engine.casting import _safe_filter
    from engine.protection import has_protection_from

    def _in_zone(obj: Any, zone: Any) -> bool:
        from engine.types import Zone

        if zone is None or any(obj is p for p in game.players):
            return True
        if zone == Zone.STACK:
            return any(obj is o for o in game.stack.objects())
        return any(zone in p.zones and p.zones[zone].contains(obj) for p in game.players)

    checked: list[Any] = []
    earlier: list[Any] = []
    index = 0
    for target in targets:
        legal = False
        while target is not None and index < len(requirements):
            requirement = requirements[index]
            index += 1
            filter_fn = getattr(requirement, "filter_fn", None)
            if (
                _in_zone(target, getattr(requirement, "zone", None))
                and (filter_fn is None or _safe_filter(filter_fn, target, earlier))
                and not has_protection_from(target, source)
            ):
                legal = True
                break
            if not getattr(requirement, "optional", False):
                break
        checked.append(target if legal else None)
        if legal:
            earlier.append(target)
    return checked


def put_reflexive_trigger(
    game: GameState,
    source: Any,
    controller: Player,
    printed: type,
    effect: Callable[..., None],
    *,
    targets: list[Any] = (),  # type: ignore[assignment]
) -> None:
    """Put a reflexive triggered ability ("when you do", rule 603.12) on the
    stack now, choosing its *targets* requirements as it goes there (rule
    603.3d); a required target with no legal choice keeps it off the stack
    (rule 603.3c). *effect* is called ``effect(game, targets, controller)`` as
    for :func:`register_enters_trigger`."""
    from engine.stack import stint_checked_targets

    requirements = list(targets)
    chosen = choose_trigger_targets(game, controller, source, requirements)
    if chosen is None:
        return
    context = capture_activation_context(game, source, controller, chosen)
    stack_obj = StackObject(
        source=source, controller=controller, printed=printed, targets=chosen, activation_context=context
    )
    stack_obj.on_resolve = lambda g: effect(
        g, still_legal_targets(g, source, requirements, stint_checked_targets(g, context, chosen)), controller
    )
    game.stack.push(stack_obj)


def register_enters_trigger(
    game: GameState,
    source: Any,
    printed: type,
    effect: Callable[..., None],
    *,
    targets: Callable[[GameState, Player], list[Any]] | None = None,
    condition: Callable[[GameState, Player], bool] | None = None,
    source_aware: bool = False,
    remember: Callable[[GameState, Player], Any] | None = None,
) -> None:
    """Register *source*'s "when this enters" triggered ability: it triggers
    as *source* enters the battlefield and uses the stack like any other.

    Everything about one occurrence is fixed as it is put on the stack and
    kept on its stack object, never read back from *source*: the controller
    (rule 603.3a), the target requirements built for that controller, and
    whatever *remember* returns — a mode chosen while targeting, say.

    *targets*, for a targeted ability, gives its target requirements for the
    fire-time controller; they are chosen as the ability is put on the stack
    (:func:`choose_trigger_targets`), and *effect* is called
    ``effect(game, targets, controller)`` with each target in order, ``None``
    for one no longer legal on resolution (rule 608.2b,
    :func:`still_legal_targets`). An untargeted *effect* is called
    ``effect(game, controller)``. *condition* is an intervening "if" clause,
    checked both as the ability triggers and as it resolves (rule 603.4).

    With *source_aware*, *effect* also gets ``source_remains=``: whether
    *source* is still the same object on the battlefield, for an effect that
    acts on it — attaching it, fighting with it, or exiling "until it leaves".
    With *remember*, it gets ``remembered=``.
    """
    from engine.events import EntersBattlefieldTriggeredEvent
    from engine.stack import battlefield_stint_id, same_stint, stint_checked_targets

    def _fires(game: GameState, event: Any) -> bool:
        if event.permanent is not source:
            return False
        return condition is None or condition(game, getattr(source, "controller", None))

    def _holds(game: GameState, controller: Player) -> bool:
        return condition is None or condition(game, controller)

    def _extras(game: GameState, stint: Any, remembered: Any) -> dict[str, Any]:
        extras: dict[str, Any] = {}
        if source_aware:
            extras["source_remains"] = same_stint(game, source, stint)
        if remember is not None:
            extras["remembered"] = remembered
        return extras

    targeting = None
    capture = None
    if targets is not None:
        requirements_now: list[list[Any]] = [[]]

        def targeting(game: GameState, event: Any, controller: Player) -> list[Any] | None:
            requirements_now[0] = list(targets(game, controller))
            return choose_trigger_targets(game, controller, source, requirements_now[0])

        def capture(game: GameState, event: Any, controller: Player) -> Any:
            return requirements_now[0], remember(game, controller) if remember is not None else None

        def _effect(game: GameState, chosen: list[Any], context: Any, state: Any) -> None:
            requirements, remembered = state
            controller = context.controller
            if _holds(game, controller):
                legal = still_legal_targets(game, source, requirements, stint_checked_targets(game, context, chosen))
                effect(game, legal, controller, **_extras(game, context.source_instance_id, remembered))

    elif source_aware or remember is not None:

        def capture(game: GameState, event: Any, controller: Player) -> Any:
            return battlefield_stint_id(game, source), remember(game, controller) if remember is not None else None

        def _effect(game: GameState, controller: Player, state: Any) -> None:
            stint, remembered = state
            if _holds(game, controller):
                effect(game, controller, **_extras(game, stint, remembered))

    else:

        def _effect(game: GameState, controller: Player) -> None:
            if _holds(game, controller):
                effect(game, controller)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_fires,
            effect=_effect,
            source=source,
            controller=getattr(source, "controller", None),
            targeting=targeting,
            capture=capture,
            printed=printed,
        )
    )


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
