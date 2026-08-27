"""Replacement effects engine — modifies events in-place with "instead" semantics.

Unlike triggered abilities (which go on the stack), replacement effects
intercept an event *before* it happens and substitute an alternative
outcome.  Key design differences from triggers:

- **No stack**: replacements are applied inline, not pushed.
- **"Instead" semantics**: the original event is replaced, not supplemented.
- **Self-replacement prevention**: each effect applies at most once per
  event to avoid infinite loops.
- **Player choice**: when multiple replacements apply to the same event,
  the affected player chooses the order via a Player Query (an ABILITY
  decision carrying the index into the matching list).
- **Subtype matching**: a replacement registered for a parent event class
  (e.g. ``MoveToGraveyardReplacementEvent``) fires for any subtype
  (e.g. ``CreatureDiesReplacementEvent``).

Public API:

- :class:`ReplacementEffect` — dataclass describing a single replacement.
- :class:`ReplacementManager` — central registry with ``register``,
  ``unregister``, and ``apply`` methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from engine.events import ReplacementEvent

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass
class ReplacementEffect:
    """Describes a single replacement effect.

    Attributes:
        event_type: The event class (or a base class) this replacement
            watches for.  A replacement registered for a parent class
            also fires when the event is an instance of a subclass.
        source: The game object (card / permanent) that owns this effect.
        condition: Optional callable ``(game, event) -> bool`` that must
            return ``True`` for the replacement to apply.
        replacement: Callable ``(game, event) -> event`` that receives the
            current event object and returns a (possibly modified) version.
        controller: The player who controls the source.
    """

    event_type: type[ReplacementEvent]
    source: Any
    condition: Callable[..., bool] | None
    replacement: Callable[..., ReplacementEvent]
    controller: Any = None


class ReplacementManager:
    """Central registry for replacement effects."""

    def __init__(self) -> None:
        self._effects: list[ReplacementEffect] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, effect: ReplacementEffect) -> None:
        """Register a replacement effect."""
        self._effects.append(effect)

    def unregister(self, source: Any) -> None:
        """Remove all replacement effects registered by *source*."""
        self._effects = [e for e in self._effects if e.source is not source]

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply(self, game: GameState, event: ReplacementEvent) -> ReplacementEvent:
        """Apply matching replacement effects to *event*.

        1. Collect all registered effects whose ``event_type`` is a
           superclass of (or equal to) the event's class and whose
           ``condition`` returns ``True``.
        2. If multiple effects match, the affected player chooses the order.
        3. Each chosen effect's ``replacement`` callable is invoked and
           the result replaces the current event.
        4. Each effect applies at most once per invocation.

        Parameters:
            game: The current game state.
            event: The typed event object to potentially modify.

        Returns:
            The (possibly modified) event after all applicable replacements.
        """
        applied: set[int] = set()

        while True:
            matching = self._collect_matching(game, event, applied)
            if not matching:
                break

            if len(matching) == 1:
                chosen = matching[0]
            else:
                affected = self._get_affected_player(game, event)
                if affected is None:
                    chosen = matching[0]
                else:
                    chosen = _choose_replacement_order(game, affected, matching)

            applied.add(id(chosen))
            event = chosen.replacement(game, event)

        return event

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_effects(self) -> list[ReplacementEffect]:
        """Return a shallow copy of all registered replacement effects."""
        return list(self._effects)

    def get_effects_for_source(self, source: Any) -> list[ReplacementEffect]:
        """Return all effects registered by *source*."""
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
        event: ReplacementEvent,
        applied: set[int],
    ) -> list[ReplacementEffect]:
        """Collect effects matching the event type that haven't been applied."""
        matching: list[ReplacementEffect] = []
        for effect in self._effects:
            if id(effect) in applied:
                continue
            if not isinstance(event, effect.event_type):
                continue
            if effect.condition is not None:
                if not effect.condition(game, event):
                    continue
            matching.append(effect)
        return matching

    @staticmethod
    def _get_affected_player(game: GameState, event: ReplacementEvent) -> Any:
        """Determine the affected player for ordering choices."""
        player = getattr(event, "player", None)
        if player is not None:
            return player
        controller = getattr(event, "controller", None)
        if controller is not None:
            return controller
        return game.active_player


def _choose_replacement_order(game: object, player: object, matching: list) -> object:
    """Raise a Player Query to pick the next replacement effect to apply.

    Replacement effects are not game objects, so they are offered as ABILITY
    decisions carrying an ``index`` into ``matching``; the Answer's index maps
    back to the chosen effect. Routed to the player's Baseline Intent in tests
    (empty source — a system-level query).
    """
    from engine.decisions import Decision
    from engine.queries import PlayerQuery, ask

    options = tuple(Decision.ability(index=i) for i in range(len(matching)))
    query = PlayerQuery(
        source=(),
        prompt="Choose replacement effect to apply next",
        options=options,
        min=1,
        max=1,
    )
    answer = ask(player, query)
    idx = dict(answer.selected[0].attrs)["index"]
    return matching[idx]
