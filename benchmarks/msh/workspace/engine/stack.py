"""The spell/ability stack with LIFO resolution and priority passing."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from engine.types import Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass(frozen=True)
class ActivationContext:
    """Immutable snapshot of an activated ability's activation-time identity.

    Captured once at activation (rule 602.2) and stored on the
    :class:`StackObject`, so an ability that is already on the stack keeps its
    activation-time controller and the *stints* of its source and targets even
    when zone changes reuse the same Python objects (see
    ``GameRefsRegistry.instance_id`` — a zone change mints a new stint id).

    A resolving effect revalidates against this context; it never re-selects
    targets. Because the context lives on the stack object (not on a mutable
    field of the source permanent), two activations of the same source may
    coexist on the stack without clobbering each other.

    Attributes:
        controller: The player who activated the ability (the ability's
            controller). "Target creature you control" is evaluated relative to
            this player, not the source's possibly-changed current controller.
        source_instance_id: The source's battlefield stint id at activation, or
            ``None`` if the source was not on the battlefield.
        target_instance_ids: The battlefield stint id of each chosen target at
            activation (``None`` for a target not on the battlefield), positionally
            aligned with :attr:`StackObject.targets`.
    """

    controller: Any
    source_instance_id: int | None = None
    target_instance_ids: tuple[int | None, ...] = ()


@dataclass
class StackObject:
    """An object on the stack representing a spell or ability.

    Attributes:
        source: The card or ability that created this stack object.
        controller: The player who controls this stack object.
        targets: The chosen targets for the spell/ability.
        on_resolve: Callback invoked when this object resolves.
        is_mana_ability: Whether this is a mana ability (resolves immediately).
        activation_context: For activated abilities, the immutable
            :class:`ActivationContext` captured at activation (``None`` for
            spells and untargeted abilities that need no revalidation).
        event_state: Immutable per-fire state a triggered ability captured when
            it was put on the stack (rule 603.3), via its
            :attr:`~engine.triggers.TriggerRegistration.capture` hook — e.g.
            Thousand-Year Storm's triggering-spell StackObject and copy count.
            ``None`` for spells and triggers with no capture hook. Owned by this
            one trigger instance, so two pending triggers of the same source do
            not share or clobber it.
        prior_qualifying_casts: For a spell StackObject that is an instant or
            sorcery cast, the number of instant/sorcery spells its controller had
            already cast this turn *before* this one — the immutable prior-cast
            count of this exact cast occurrence, captured at the authoritative
            cast site (:func:`engine.casting.cast_spell` / ``cast_spell_free``)
            from :meth:`engine.player.Player.record_instant_or_sorcery_cast`.
            Because each cast mints a new StackObject (a recast object leaves and
            returns), this count belongs to the occurrence, not the mutable card,
            and is read directly by Thousand-Year Storm rather than reconstructed
            by excluding the triggering spell from cast history by identity.
            ``None`` for anything that is not a qualifying-spell cast (copies —
            which are not casts — abilities, triggers, and permanent spells).
        departure_zone: For a spell whose *stack-departure* destination is
            overridden by the way it was cast: a spell cast via flashback is
            exiled instead of being put anywhere else **any time it would leave
            the stack** (rule 702.34a) — when it resolves, when it is countered,
            and when it fizzles alike. The override is a property of this one
            cast occurrence, so it rides on the StackObject (like
            ``activation_context`` / ``prior_qualifying_casts``), never on the
            mutable card. ``None`` uses the caller's default (permanents →
            battlefield on resolution, otherwise → owner's graveyard). Set only
            by an explicit cast mode (``cast_spell_free(...,
            mode=CastMode.FLASHBACK)``) and applied by
            :func:`move_spell_off_stack` — the single primitive through which
            every spell leaves the stack.
        is_spell: ``True`` iff this stack object is a **spell** — a cast
            occurrence pushed by :func:`engine.casting.cast_spell` /
            ``cast_spell_free``, or a spell copy from :func:`copy_spell`
            (a copy of a spell is a spell on the stack, rule 707.10a).
            Triggered and activated abilities keep the default ``False``: an
            ability may share its ``source`` card with a pending spell, but it
            is not that spell — "counter target spell" effects and
            ``Zone.STACK`` target enumeration select spell occurrences by this
            flag, never by inspecting the shared source card.
    """

    source: Any
    controller: Player
    targets: list[Any] = field(default_factory=list)
    on_resolve: Callable[[GameState], None] = field(default=lambda _game: None)
    is_mana_ability: bool = False
    activation_context: ActivationContext | None = None
    event_state: Any = None
    prior_qualifying_casts: int | None = None
    departure_zone: Zone | None = None
    is_spell: bool = False


# ---------------------------------------------------------------------------
# Activation-time identity: stint capture and resolution-time revalidation
# ---------------------------------------------------------------------------
#
# These are the *single* shared mechanism for capturing an activated/triggered
# ability's activation-time identity and revalidating its captured targets when
# it resolves (rule 602.2 / 608.2b / 608.2c). Every targeted activated ability,
# loyalty ability, and triggered ability captures its context through
# :func:`capture_activation_context` and, at resolution, keeps only the targets
# :func:`surviving_targets` returns — the targets are never re-selected.
#
# A zone change mints a fresh *stint* id (see ``GameRefsRegistry.instance_id``),
# so comparing a target's current-zone stint id against the one captured at
# activation is what distinguishes "the same object I targeted" from "a new
# object in the same Python instance" after a leave-and-return (invariant: a
# battlefield object that leaves and returns is a new object for targeting).


def object_current_zone(game: GameState, obj: Any) -> str | None:
    """Return the zone value (e.g. ``"battlefield"``) *obj* currently occupies,
    or ``None`` if it is in no player's zone.

    Zone-generic on purpose: a captured target may be a battlefield permanent
    (creatures) or a card in a graveyard (Scavenging Ooze), and both must be
    revalidated by the same helper.

    A :class:`StackObject` target (a spell targeted on the stack — counterspell
    targets are exact cast occurrences, never source cards) occupies ``"stack"``
    exactly while **that occurrence** is on ``game.stack`` (identity), and no
    zone once it departs. A StackObject never re-enters the stack — a recast
    mints a new occurrence — so the same-stint check makes a departed occurrence
    permanently illegal even when its source card is back in a stack zone.
    """
    if isinstance(obj, StackObject):
        return Zone.STACK.value if game.stack.contains(obj) else None
    for player in game.players:
        zones = player.zones
        for zone in Zone:
            if zone in zones and zones[zone].contains(obj):
                return zone.value
    return None


def object_stint_id(game: GameState, obj: Any) -> int | None:
    """Return the instance id of *obj*'s current-zone stint, or ``None`` if it
    is in no zone. Used to snapshot a target's identity at activation."""
    zone_value = object_current_zone(game, obj)
    if zone_value is None:
        return None
    return game.refs.instance_id(obj, zone_value)


def battlefield_stint_id(game: GameState, obj: Any) -> int | None:
    """Return the instance id of *obj*'s current battlefield stint, or ``None``
    if it is not on any player's battlefield (used to snapshot the source)."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return game.refs.instance_id(obj, Zone.BATTLEFIELD.value)
    return None


def capture_activation_context(
    game: GameState,
    source: Any,
    controller: Any,
    targets: list[Any],
) -> ActivationContext:
    """Snapshot the activation-time controller and the source/target stints
    (rule 602.2). Stored on the :class:`StackObject`, never on the mutable
    source. Target stints are captured zone-generically so a graveyard-card
    target is revalidated the same way a battlefield permanent is."""
    return ActivationContext(
        controller=controller,
        source_instance_id=battlefield_stint_id(game, source),
        target_instance_ids=tuple(object_stint_id(game, t) for t in targets),
    )


def same_stint(game: GameState, obj: Any, stint_id: int | None) -> bool:
    """Return ``True`` if *obj* is currently in the *same* zone-stint captured
    as *stint_id* at activation.

    ``False`` when *obj* has left its zone, or left and returned (a new stint,
    hence a new instance id). A ``stint_id`` of ``None`` — the object was in no
    zone at activation — never matches, **except** for a player: players are not
    zone residents and their identity is stable, so a targeted player is always
    "the same" (any legality restriction is left to the caller's predicate).
    """
    if any(obj is player for player in game.players):
        return True
    if stint_id is None:
        return False
    zone_value = object_current_zone(game, obj)
    if zone_value is None:
        return False
    return game.refs.instance_id(obj, zone_value) == stint_id


def surviving_targets(
    game: GameState,
    context: ActivationContext | None,
    targets: list[Any],
    is_legal: Callable[[Any], bool] | None = None,
) -> list[Any]:
    """Return the subset of *targets* still legal at resolution (rule 608.2b/2c).

    A target survives iff **both**:

    1. it is in the *same zone-stint* captured at activation
       (:func:`same_stint`) — a leave-and-return mints a new stint and fails
       this, so a departed-and-returned object is rejected; and
    2. it satisfies *is_legal* — a predicate expressing the *complete*
       targeting restriction, evaluated relative to ``context.controller`` for
       "you control"-style requirements (never the source's mutable current
       controller).

    Callers apply the effect only to the returned targets. When the list is
    empty every target was illegal and the effect does nothing (rule 608.2c).
    """
    survivors: list[Any] = []
    ids = context.target_instance_ids if context is not None else ()
    for i, target in enumerate(targets):
        stint = ids[i] if i < len(ids) else None
        if not same_stint(game, target, stint):
            continue
        if is_legal is not None and not is_legal(target):
            continue
        survivors.append(target)
    return survivors


def stint_checked_targets(
    game: GameState,
    context: ActivationContext | None,
    targets: list[Any],
) -> list[Any]:
    """Return a **position-preserving** copy of *targets* in which any target no
    longer in the same zone-stint captured at activation is replaced by ``None``.

    Unlike :func:`surviving_targets` (which drops illegal targets and is used by
    activated/loyalty/triggered abilities that iterate a flat legal list), this
    keeps each target at its original index so a spell with **heterogeneous or
    dependent** targets — e.g. Fiery Annihilation's ``[creature, Equipment]`` —
    can still read ``chosen[0]`` / ``chosen[1]`` by position after a
    leave-and-return nulls one of them. A ``None`` at a position reads as "that
    target is illegal": the object's own predicate re-check (``getattr(None,
    …)`` yields empty) then does nothing for it. When *context* is ``None`` (a
    stack object that captured none) the targets are returned unchanged; spell
    copies **do** carry their own context (see :func:`copy_spell`) and are
    revalidated by this same pass.
    """
    if context is None:
        return list(targets)
    ids = context.target_instance_ids
    checked: list[Any] = []
    for i, target in enumerate(targets):
        stint = ids[i] if i < len(ids) else None
        checked.append(target if same_stint(game, target, stint) else None)
    return checked


class Stack:
    """The game stack — a LIFO structure for spells and abilities.

    The internal list stores objects with the last element being the top
    of the stack (most recently pushed).
    """

    def __init__(self) -> None:
        self._items: list[StackObject] = []

    def push(self, obj: StackObject) -> None:
        """Push *obj* onto the top of the stack."""
        self._items.append(obj)

    def pop(self) -> StackObject:
        """Remove and return the top object from the stack.

        Raises:
            IndexError: If the stack is empty.
        """
        return self._items.pop()

    def peek(self) -> StackObject | None:
        """Return the top object without removing it, or ``None`` if empty."""
        return self._items[-1] if self._items else None

    def __len__(self) -> int:
        """Return the number of objects on the stack."""
        return len(self._items)

    def is_empty(self) -> bool:
        """Return ``True`` if the stack contains no objects."""
        return len(self._items) == 0

    def objects(self) -> list[StackObject]:
        """Return all stack objects ordered from top to bottom."""
        return list(reversed(self._items))

    def contains(self, obj: Any) -> bool:
        """Return ``True`` iff exactly *obj* is on the stack, by **identity**.

        Never by equality — StackObject is a dataclass whose ``==`` compares
        fields, and two casts of the same card are distinct occurrences that
        must never be conflated.
        """
        return any(item is obj for item in self._items)

    def remove_object(self, obj: Any) -> bool:
        """Remove exactly *obj* from the stack, by **identity**, at most once.

        Returns ``True`` if it was found and removed, ``False`` otherwise.
        The identity-based counterpart of ``list.remove`` (which would use
        dataclass field equality and could remove a different occurrence).
        """
        for i, item in enumerate(self._items):
            if item is obj:
                self._items.pop(i)
                return True
        return False

    def has_source(self, source: Any) -> bool:
        """Return ``True`` if any stack object's source is *source* (identity)."""
        return any(obj.source is source for obj in self._items)

    def pop_by_source(self, source: Any) -> StackObject | None:
        """Remove and return the topmost stack object whose source is *source*.

        Returns ``None`` if no stack object has that source. Used by replay
        validation to resolve the pending object for a specific card when
        GRE reports its resolution out of engine stack order.
        """
        for i in range(len(self._items) - 1, -1, -1):
            if self._items[i].source is source:
                return self._items.pop(i)
        return None


def move_spell_off_stack(
    game: GameState,
    stack_obj: StackObject,
    to_zone: Zone = Zone.GRAVEYARD,
    *,
    resolving: bool = False,
) -> bool:
    """Move the spell represented by *stack_obj* off the stack.

    The single engine primitive for **every** way a spell leaves the stack, so
    the cast's departure replacement (``StackObject.departure_zone`` — a
    flashback spell is exiled any time it would leave the stack, rule 702.34a)
    is honoured uniformly. Two callers:

    * **Resolution** (``resolving=True``) — :func:`engine.casting._resolve_spell`,
      after the resolver has already popped *stack_obj*. *to_zone* is the
      type-default destination (battlefield for a permanent spell, graveyard
      otherwise).
    * **Countering** (``resolving=False``, the default) — a counterspell effect,
      with *stack_obj* still on the stack. The default *to_zone* sends an
      ordinary countered spell to its owner's graveyard (rule 701.5a).

    Contract:

    1. If *stack_obj* is still on the stack it is removed — exactly that object,
       by identity, exactly once. When ``resolving=False`` and *stack_obj* is
       **not** on the stack, the spell has already departed (it resolved or was
       countered earlier): nothing happens and ``False`` is returned, so a
       fizzled counter can never move a card that has since been re-cast (the
       card's stack-zone presence belongs to the new cast occurrence, not this
       one).
    2. The destination is ``stack_obj.departure_zone or to_zone`` — the
       flashback exile replacement applies to resolution and countering alike.
    3. The card is moved through :func:`engine.zones.move_to_zone`
       (STACK → destination): removed from whichever player's stack zone holds
       it and added to its **owner's** destination zone (its controller's for
       battlefield entry), advancing its zone epoch.
    4. The card is moved at most once. If it occupies no stack zone — the
       resolution effect already moved it, or *stack_obj* is a spell copy
       (whose card object never occupies a stack zone; copies cease to exist,
       rule 707.10a) — nothing moves.

    Returns:
        ``True`` if *stack_obj* departed the stack via this call (including a
        copy, which departs without a card move); ``False`` only on the
        countering fizzle path (``resolving=False`` with *stack_obj* no longer
        on the stack).
    """
    from engine.zones import move_to_zone

    if not game.stack.remove_object(stack_obj) and not resolving:
        # Countering fizzle: this occurrence already left the stack.
        return False

    card = stack_obj.source
    if any(p.zones[Zone.STACK].contains(card) for p in game.players):
        destination = stack_obj.departure_zone or to_zone
        move_to_zone(game, card, Zone.STACK, destination)
    return True


def copy_spell(
    game: GameState,
    original: StackObject,
    controller: Player,
    new_targets: list[Any] | None = None,
) -> StackObject:
    """Create a copy of a spell on the stack (for storm and similar effects).

    Shallow-copies the source card so the copy has independent state
    (chosen_targets, etc.) while sharing class method bindings.  Binds
    on_resolve to call the copied card's on_resolve directly — no zone
    movement, which is correct for spell copies.

    The copy carries its own :class:`ActivationContext` so its targets are
    stint-revalidated at resolution exactly like a normally-cast spell (rule
    608.2b):

    * **Retaining the original's targets** (``new_targets is None``) — the copy
      *inherits the original's captured target stint ids* (not fresh ones), so a
      retained target that left and returned between the original's cast and the
      copy's resolution is rejected. The context's controller is the copy's
      controller ("you control" is judged for the copy's controller).
    * **Choosing new targets** (``new_targets`` given) — the copy captures those
      new targets' *current* stints, since they were selected as the copy was
      created.

    Args:
        game: The current game state.
        original: The StackObject being copied.
        controller: The player who controls the copy.
        new_targets: Optional replacement targets.  If ``None``, the
            original's target list is cloned.

    Returns:
        A new StackObject representing the copy ready to be pushed.
    """
    copied_card = copy.copy(original.source)
    copied_card.controller = controller
    copied_card.owner = getattr(original.source, "owner", controller)

    if new_targets is not None:
        # New targets chosen for the copy — capture their current stints.
        targets = list(new_targets)
        context: ActivationContext | None = capture_activation_context(
            game, copied_card, controller, targets
        )
    else:
        # Retained targets — inherit the original's captured stint ids so a
        # leave-and-return is still rejected. Fall back to a fresh capture if the
        # original carried no context (e.g. an ability copy).
        targets = list(original.targets)
        orig_ctx = original.activation_context
        if orig_ctx is not None:
            context = ActivationContext(
                controller=controller,
                source_instance_id=orig_ctx.source_instance_id,
                target_instance_ids=orig_ctx.target_instance_ids,
            )
        else:
            context = capture_activation_context(
                game, copied_card, controller, targets
            )

    copy_obj = StackObject(
        source=copied_card,
        controller=controller,
        targets=targets,
        activation_context=context,
        # A copy of a spell is a spell on the stack (rule 707.10a): it can be
        # targeted/countered like the original. Its departure_zone stays None —
        # a copy is not a flashback cast even when the original was.
        is_spell=True,
    )

    def _copy_resolve(g: GameState) -> None:
        # Stint-revalidate (position-preserving) before the copy resolves, the
        # same check _resolve_spell applies to a normal cast.
        copied_card.chosen_targets = stint_checked_targets(
            g, copy_obj.activation_context, copy_obj.targets
        )
        copied_card.on_resolve(g)

    copy_obj.on_resolve = _copy_resolve
    return copy_obj


def check_state_based_actions(game: GameState) -> None:
    """Check and perform all state-based actions until the game state is stable.

    This is a convenience wrapper around
    :func:`engine.state_based_actions.resolve_state_based_actions` that
    maintains the original ``-> None`` call-site contract used by
    :func:`priority_loop`.  For the single-pass boolean API, import
    :func:`~engine.state_based_actions.check_state_based_actions` directly
    from :mod:`engine.state_based_actions`.
    """
    from engine.state_based_actions import resolve_state_based_actions

    resolve_state_based_actions(game)


def _rederive_continuous_effects(game: GameState) -> None:
    """Re-derive continuous characteristics from scratch (reset then reapply).

    Always runs a full pass — it does **not** short-circuit on an empty effect
    manager. A resolution (or an SBA) may have removed the last active effect,
    in which case a reset is still required so a departed buff does not stay
    baked into a permanent's modified characteristics. ``apply_all`` resets
    every battlefield object to its base characteristics before reapplying, so
    an empty manager cleanly strips all continuous modifications.
    """
    effect_manager = getattr(game, "effect_manager", None)
    if effect_manager is not None:
        effect_manager.apply_all(game)


def settle_after_resolution(game: GameState) -> None:
    """Bring the game to a stable state after a stack object resolves.

    Ordering (rule 608.2g → 704): re-derive continuous effects *before* SBAs so
    every SBA inspects current characteristics (toughness, lethal damage,
    attachment legality). Then loop: run one SBA pass and, whenever it changes
    the board, re-derive again so the next pass — and the state visible when
    priority returns — is never checked against pre-recalculation characteristics.

    The loop always ends on a re-derive with no subsequent SBA change, so a 2/2
    that a resolving +2/+2 turns into a damaged 4/4 survives (re-derive precedes
    the lethal-damage check), a resolving -2/-2 sends a 2/2 to the graveyard
    before priority returns (re-derive precedes the zero-toughness check), and
    removing the last effect during resolution resets the permanent.

    ``resolve_state_based_actions`` is the full SBA settler (its own inner loop
    runs checks until stable and repeats while triggers are queued, per rule
    704.3); wrapping it in the re-derive loop guarantees the *first* SBA check
    each round sees freshly re-derived characteristics. The loop terminates:
    SBAs only remove permanents / decrement counters, and re-derivation is
    deterministic, so the state cannot oscillate.
    """
    from engine.state_based_actions import resolve_state_based_actions

    while True:
        _rederive_continuous_effects(game)
        if not resolve_state_based_actions(game):
            break


def resolve_top_of_stack(game: GameState) -> None:
    """Pop and resolve exactly one stack object, then settle the game.

    This is the single, canonical normal-game resolution primitive shared by
    :func:`priority_loop` (the normal-game path), :func:`engine.casting.resolve_top`
    (a thin delegating alias), and the test-suite stack resolver — so settlement
    behaviour is identical at every entry point.

    Sequence:

    1. Pop and resolve exactly one stack object.
    2. Re-derive continuous effects immediately (so an effect the resolution
       just registered — e.g. Adventuring Gear's landfall +2/+2 — applies now).
    3. Run state-based actions until stable, re-deriving between passes so SBAs
       never inspect stale characteristics and any board change they cause leaves
       continuous characteristics current before priority returns.

    See :func:`settle_after_resolution` for the ordering rationale.
    """
    if game.stack.is_empty():
        return
    obj = game.stack.pop()
    obj.on_resolve(game)
    settle_after_resolution(game)


def _get_legal_actions(game: GameState, player: Player) -> list[Any]:
    """Return the legal actions available to *player*.

    Placeholder — returns an empty list until spells/abilities are
    implemented in later items.
    """
    return []


def _handle_priority(game: GameState, player: Player) -> bool:
    """Give priority to *player* and let them act or pass.

    Returns ``True`` if the player passed priority, ``False`` if they
    took an action (in which case the priority loop restarts).

    Priority is *action-layer* and directive-driven: the engine never elicits a
    proactive priority action from the player through a Player Query. Spells and
    abilities are cast/activated imperatively (by a test or the replay
    executor), not via a priority choice, so the player simply passes priority
    here. Only the *choice* layer (targets, modes, ordering, …) is query-driven.
    """
    return True


def priority_loop(game: GameState) -> None:
    """Run the priority-passing loop for the current phase/step.

    Flow
    ----
    1. Active player gets priority.  They may play spells/abilities
       (pushed to stack) or pass.
    2. When a player takes an action they **retain** priority (MTG rule:
       the player who just acted gets to respond first).
    3. When a player passes, priority moves to the other player.
    4. If both players pass in succession with the stack **non-empty**,
       the top of the stack is resolved (``pop`` → ``on_resolve(game)``),
       state-based actions are checked, and the active player receives
       priority again.
    5. If both players pass with the stack **empty**, return (the game
       advances to the next phase/step).

    ``game.priority_player_index`` is kept in sync throughout so that
    :pyattr:`GameState.priority_player` always reflects who currently
    holds priority.

    Priority is action-layer and directive-driven: the engine never
    elicits a proactive priority action via a Player Query — the player
    simply passes priority here (see :func:`_handle_priority`). Spells
    and abilities are cast/activated imperatively by callers (tests or a
    replay executor), and the *choice* layer (targets, modes, ordering,
    …) is the only query-driven surface.
    """
    while True:
        # Active player receives priority at the start of each
        # resolution round.
        current_index = game.active_player_index
        game.priority_player_index = current_index
        consecutive_passes = 0

        while consecutive_passes < 2:
            player = game.players[current_index]
            game.priority_player_index = current_index

            passed = _handle_priority(game, player)

            if passed:
                consecutive_passes += 1
                # Priority moves to the other player.
                current_index = 1 - current_index
            else:
                # Player took an action — they retain priority.
                consecutive_passes = 0

        # Both players passed consecutively.
        if game.stack.is_empty():
            return  # Advance to next phase/step

        # Resolve top of stack (LIFO) — settles SBAs and re-derives continuous
        # effects so a just-registered mid-turn effect applies immediately.
        resolve_top_of_stack(game)
        # Active player receives priority again — outer loop continues.
