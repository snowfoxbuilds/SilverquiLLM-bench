"""Replacement effects engine — modifies events in-place with "instead" semantics.

Unlike triggered abilities (which go on the stack), replacement effects
intercept an event *before* it happens and substitute an alternative
outcome.  Key design differences from triggers:

- **No stack**: replacements are applied inline, not pushed.
- **"Instead" semantics**: the original event is replaced, not supplemented.
- **Self-replacement prevention**: each effect applies at most once per
  event to avoid infinite loops.
- **Player choice**: when multiple replacements apply to the same event,
  the affected player chooses the order via ``Player.choose``.

Public API:

- :class:`ReplacementEffect` — dataclass describing a single replacement.
- :class:`ReplacementManager` — central registry with ``register``,
  ``unregister``, and ``apply`` methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass
class ReplacementEffect:
    """Describes a single replacement effect.

    Attributes:
        event_type: The event type string this replacement watches for
            (e.g. ``"creature_dies"``).
        source: The game object (card / permanent) that owns this effect.
        condition: Optional callable ``(game, event_data) -> bool`` that
            must return ``True`` for the replacement to apply.  ``None``
            means the replacement always applies for its event type.
        replacement: Callable ``(game, event_data) -> event_data`` that
            receives the current event data dict and returns a (possibly
            modified) version.  This callable implements the "instead"
            logic.
        controller: The player who controls the source.  Used to determine
            who the "affected player" is when multiple replacements compete.
    """

    event_type: str
    source: Any
    condition: Callable[..., bool] | None
    replacement: Callable[..., dict[str, Any]]
    controller: Player | None = None


class ReplacementManager:
    """Central registry for replacement effects.

    Replacement effects are registered when a permanent enters the
    battlefield (via ``card.register_replacement_effects(game)``) and
    unregistered when the source leaves.

    :meth:`apply` checks all registered effects matching the given
    event type, evaluates conditions, and applies the matching
    replacements to the event data.  If multiple replacements match,
    the affected player chooses the application order.

    Each replacement effect can apply at most **once per event** to
    prevent infinite self-replacement loops.
    """

    def __init__(self) -> None:
        self._effects: list[ReplacementEffect] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, effect: ReplacementEffect) -> None:
        """Register a replacement effect.

        Parameters:
            effect: The :class:`ReplacementEffect` to add.
        """
        self._effects.append(effect)

    def unregister(self, source: Any) -> None:
        """Remove all replacement effects registered by *source* (identity-based).

        Called when a permanent leaves the battlefield.

        Parameters:
            source: The game object whose effects should be removed.
        """
        self._effects = [e for e in self._effects if e.source is not source]

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply(
        self,
        game: GameState,
        event_type: str,
        event_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply matching replacement effects to *event_data*.

        1. Collect all registered effects whose ``event_type`` matches and
           whose ``condition`` (if any) returns ``True``.
        2. If multiple effects match, the affected player chooses the order
           via ``Player.choose``.
        3. Each chosen effect's ``replacement`` callable is invoked with
           ``(game, event_data)`` and the result replaces the current
           ``event_data``.
        4. **Self-replacement prevention**: each effect is applied at most
           once per invocation.

        Parameters:
            game: The current game state.
            event_type: The event type string (e.g. ``"creature_dies"``).
            event_data: A mutable dict of event-specific data.

        Returns:
            The (possibly modified) *event_data* dict after all applicable
            replacements have been applied.
        """
        # Track which effects have already been applied (self-replacement prevention).
        applied: set[int] = set()  # ids of ReplacementEffect objects

        # Iterate: after each application, re-check for newly applicable effects.
        # This allows chained replacements while preventing self-loops.
        while True:
            matching = self._collect_matching(game, event_type, event_data, applied)
            if not matching:
                break

            if len(matching) == 1:
                chosen = matching[0]
            else:
                # Affected player chooses order.  Determine affected player
                # from event_data, falling back to active player.
                affected = self._get_affected_player(game, event_data)
                chosen = affected.choose(
                    matching,
                    "Choose replacement effect order",
                )

            applied.add(id(chosen))
            event_data = chosen.replacement(game, event_data)

        return event_data

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_effects(self) -> list[ReplacementEffect]:
        """Return a shallow copy of all registered replacement effects."""
        return list(self._effects)

    def get_effects_for_source(self, source: Any) -> list[ReplacementEffect]:
        """Return all effects registered by *source* (identity-based)."""
        return [e for e in self._effects if e.source is source]

    def clear(self) -> None:
        """Remove all registered replacement effects."""
        self._effects.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_matching(
        self,
        game: GameState,
        event_type: str,
        event_data: dict[str, Any],
        applied: set[int],
    ) -> list[ReplacementEffect]:
        """Collect effects matching *event_type* that haven't been applied yet."""
        matching: list[ReplacementEffect] = []
        for effect in self._effects:
            if id(effect) in applied:
                continue
            if effect.event_type != event_type:
                continue
            if effect.condition is not None:
                if not effect.condition(game, event_data):
                    continue
            matching.append(effect)
        return matching

    @staticmethod
    def _get_affected_player(
        game: GameState,
        event_data: dict[str, Any],
    ) -> Any:
        """Determine the affected player for ordering choices.

        Checks ``event_data`` for ``"player"`` or ``"controller"`` keys;
        falls back to the game's active player.
        """
        if "player" in event_data:
            return event_data["player"]
        if "controller" in event_data:
            return event_data["controller"]
        return game.active_player
