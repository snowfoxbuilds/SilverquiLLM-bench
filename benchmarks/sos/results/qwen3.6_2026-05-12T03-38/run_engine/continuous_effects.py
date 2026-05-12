"""Continuous effects and the 7-layer system.

Implements the MTG layer system (rule 613) for applying continuous effects
in the correct order. Effects are applied in layer order, and within the
same layer/sublayer, in timestamp order.

Phase 1 scope:
  - Layers 4 (type-changing), 6 (ability granting/removing), 7c (P/T
    modifications), and 7d (P/T from counters) are fully functional.
  - Layers 1 (copy), 2 (control), 3 (text), and 5 (color) are stubs
    that iterate effects but delegate to their ``apply`` callables.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from engine.game_state import GameState


class Layer(enum.IntEnum):
    """The 7 layers for applying continuous effects (rule 613).

    Using IntEnum so that effects are naturally sorted by layer order.
    """

    COPY = 1
    CONTROL = 2
    TEXT = 3
    TYPE = 4
    COLOR = 5
    ABILITY = 6
    POWER_TOUGHNESS = 7


class SubLayer(enum.Enum):
    """Sub-layers for layer 7 (power/toughness) effects.

    Per rule 613.4:
      - 7a: Characteristic-defining abilities that set P/T.
      - 7b: Effects that set P/T to specific values.
      - 7c: Effects that modify P/T (e.g. +2/+2).
      - 7d: P/T changes from counters.
    """

    CHARACTERISTIC_DEFINING = "7a"
    SET_PT = "7b"
    MODIFY_PT = "7c"
    COUNTERS = "7d"


# Duration constants — sentinels for ContinuousEffect.duration.
DURATION_PERMANENT = -1
"""The effect lasts as long as its source is on the battlefield."""

DURATION_END_OF_TURN = 0
"""The effect lasts until end of turn (removed during cleanup)."""


@dataclass
class ContinuousEffect:
    """A single continuous effect in the layer system.

    Attributes:
        source: The game object that creates this effect.
        layer: Which of the 7 layers this effect belongs to.
        sublayer: Sub-layer within layer 7 (``None`` for layers 1–6).
        apply: Callable ``(game: GameState) -> None`` that applies the effect.
        timestamp: Monotonically increasing integer for ordering effects
            within the same layer. Lower timestamp means earlier.
        duration: How long the effect lasts.  Use :data:`DURATION_PERMANENT`
            for static abilities, :data:`DURATION_END_OF_TURN` for until-EOT
            effects, or a positive integer representing the turn number
            on which the effect expires (removed when
            ``game.turn_number > duration``).
    """

    source: Any
    layer: Layer
    sublayer: SubLayer | None = None
    apply: Callable[..., Any] = field(default=lambda _game: None)
    timestamp: int = 0
    duration: int = DURATION_PERMANENT

    def _sort_key(self) -> tuple[int, int, int]:
        """Return a sort key: (layer, sublayer-ordinal, timestamp).

        Effects are sorted first by layer, then by sublayer (for layer 7),
        then by timestamp within the same (layer, sublayer).
        """
        sublayer_order = _SUBLAYER_ORDER.get(self.sublayer, 0) if self.sublayer else 0
        return (self.layer.value, sublayer_order, self.timestamp)


# Map SubLayer values to a numeric ordering so 7a < 7b < 7c < 7d.
_SUBLAYER_ORDER: dict[SubLayer, int] = {
    SubLayer.CHARACTERISTIC_DEFINING: 1,
    SubLayer.SET_PT: 2,
    SubLayer.MODIFY_PT: 3,
    SubLayer.COUNTERS: 4,
}


class EffectManager:
    """Manages all active continuous effects and applies them in layer order.

    The manager holds a list of :class:`ContinuousEffect` objects and provides
    methods to add, remove expired effects, and apply them all to the game
    state in the correct layer/timestamp order.
    """

    def __init__(self) -> None:
        self._effects: list[ContinuousEffect] = []
        self._next_timestamp: int = 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, effect: ContinuousEffect) -> ContinuousEffect:
        """Add a continuous effect, auto-assigning a timestamp if it's 0.

        Args:
            effect: The effect to register.

        Returns:
            The effect (with timestamp populated).
        """
        if effect.timestamp == 0:
            effect.timestamp = self._next_timestamp
            self._next_timestamp += 1
        else:
            # Keep _next_timestamp ahead of any manually assigned timestamps.
            if effect.timestamp >= self._next_timestamp:
                self._next_timestamp = effect.timestamp + 1
        self._effects.append(effect)
        return effect

    def remove(self, effect: ContinuousEffect) -> bool:
        """Remove a specific effect by identity.

        Returns:
            ``True`` if the effect was found and removed, ``False`` otherwise.
        """
        for i, e in enumerate(self._effects):
            if e is effect:
                self._effects.pop(i)
                return True
        return False

    def remove_expired(self, game: GameState) -> int:
        """Remove effects whose duration has expired.

        - ``DURATION_PERMANENT`` (−1): never expires automatically.
        - ``DURATION_END_OF_TURN`` (0): removed when this method is called
          (typically during the cleanup step).
        - Positive integer *n*: removed when ``game.turn_number > n``.

        Args:
            game: The current game state (used for turn number).

        Returns:
            The number of effects removed.
        """
        before = len(self._effects)
        remaining: list[ContinuousEffect] = []
        for eff in self._effects:
            if eff.duration == DURATION_PERMANENT:
                remaining.append(eff)
            elif eff.duration == DURATION_END_OF_TURN:
                # End-of-turn effects are swept away.
                continue
            elif game.turn_number > eff.duration:
                # Turn-numbered expiry.
                continue
            else:
                remaining.append(eff)
        self._effects = remaining
        return before - len(self._effects)

    def apply_all(self, game: GameState) -> None:
        """Apply all active effects in layer order, then timestamp order.

        Before applying, all objects on each player's battlefield are reset
        to their original (pre-effect) characteristics so that calling this
        method multiple times is idempotent.

        Within each layer (and sublayer for layer 7), effects are applied
        in timestamp order.  This method should be called whenever the
        game state needs a fresh recalculation of continuous effects —
        for example, after state-based actions or any game event that
        could change the set of applicable effects.
        """
        # Reset battlefield objects to their base characteristics so that
        # reapplying effects does not accumulate on top of stale mutations.
        self._reset_objects(game)

        sorted_effects = sorted(self._effects, key=lambda e: e._sort_key())
        for effect in sorted_effects:
            effect.apply(game)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset_objects(self, game: GameState) -> None:
        """Reset all battlefield objects to their original characteristics.

        Iterates over every player's battlefield and calls
        ``_reset_characteristics()`` on any object that supports it
        (i.e. :class:`~engine.card.CardImpl` and its subclasses).
        """
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                reset = getattr(obj, "_reset_characteristics", None)
                if callable(reset):
                    reset()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @property
    def effects(self) -> list[ContinuousEffect]:
        """Return a shallow copy of the current effects list."""
        return list(self._effects)

    def get_effects_for_layer(self, layer: Layer) -> list[ContinuousEffect]:
        """Return effects belonging to a specific layer, in timestamp order."""
        return sorted(
            [e for e in self._effects if e.layer == layer],
            key=lambda e: e._sort_key(),
        )

    def get_effects_by_source(self, source: Any) -> list[ContinuousEffect]:
        """Return all effects created by a given source object."""
        return [e for e in self._effects if e.source is source]

    def clear(self) -> None:
        """Remove all effects."""
        self._effects.clear()

    def __len__(self) -> int:
        return len(self._effects)
