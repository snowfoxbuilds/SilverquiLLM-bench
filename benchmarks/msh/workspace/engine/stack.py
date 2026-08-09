"""The spell/ability stack with LIFO resolution and priority passing."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

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
    """

    source: Any
    controller: Player
    targets: list[Any] = field(default_factory=list)
    on_resolve: Callable[[GameState], None] = field(default=lambda _game: None)
    is_mana_ability: bool = False
    activation_context: ActivationContext | None = None


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

    targets = new_targets if new_targets is not None else list(original.targets)

    copy_obj = StackObject(
        source=copied_card,
        controller=controller,
        targets=targets,
    )

    def _copy_resolve(g: GameState) -> None:
        copied_card.chosen_targets = copy_obj.targets
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
