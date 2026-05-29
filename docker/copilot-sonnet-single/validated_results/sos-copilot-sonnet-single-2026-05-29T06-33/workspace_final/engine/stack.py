"""The spell/ability stack with LIFO resolution and priority passing."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass
class StackObject:
    """An object on the stack representing a spell or ability.

    Attributes:
        source: The card or ability that created this stack object.
        controller: The player who controls this stack object.
        targets: The chosen targets for the spell/ability.
        on_resolve: Callback invoked when this object resolves.
        is_mana_ability: Whether this is a mana ability (resolves immediately).
    """

    source: Any
    controller: Player
    targets: list[Any] = field(default_factory=list)
    on_resolve: Callable[[GameState], None] = field(default=lambda _game: None)
    is_mana_ability: bool = False


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

    def remove(self, obj: StackObject) -> None:
        """Remove *obj* from the stack (identity-based lookup).

        Raises:
            ValueError: If *obj* is not on the stack.
        """
        for i, item in enumerate(self._items):
            if item is obj:
                del self._items[i]
                return
        raise ValueError(f"{obj!r} not on the stack")


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

    When the stack is non-empty, the player is always asked via
    :meth:`Player.choose` so they can respond.  When the stack is empty
    and no legal actions exist, the player auto-passes.
    """
    actions = _get_legal_actions(game, player)

    # Auto-pass when there is nothing to respond to and no actions.
    if not actions and game.stack.is_empty():
        return True

    options = actions + ["pass"]
    choice = player.choose(options, "priority: choose action or pass")

    if choice == "pass":
        return True

    # Mana abilities resolve immediately without using the stack.
    if isinstance(choice, StackObject) and choice.is_mana_ability:
        choice.on_resolve(game)
        return False

    # Regular spell / ability — push onto the stack.
    if isinstance(choice, StackObject):
        game.stack.push(choice)

    return False


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

    Player decisions come from :meth:`Player.choose`.  When no legal
    actions exist and the stack is empty, the player auto-passes without
    being asked.
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

        # Resolve top of stack (LIFO).
        obj = game.stack.pop()
        obj.on_resolve(game)
        check_state_based_actions(game)
        # Active player receives priority again — outer loop continues.
