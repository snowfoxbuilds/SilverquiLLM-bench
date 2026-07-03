"""Card implementation for Scathing Shadelock // Venomous Words."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ScathingShadelock(Creature):
    """Scathing Shadelock — {4}{B} — Creature — Snake Warlock 4/6.

    At the beginning of your first main phase, this creature becomes prepared.
    (While prepared, you may cast a copy of its spell side. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scathing Shadelock")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault("subtypes", {"Snake", "Warlock"})
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_phase_trigger(self, game: "GameState", phase: str) -> None:
        """Trigger at the beginning of first main phase to become prepared."""
        if phase == "first_main":
            self.prepared = True

    def can_cast_spell_copy(self, game: "GameState") -> bool:
        """Return whether a spell copy can be cast (must be prepared)."""
        return self.prepared

    def cast_spell_copy(self, game: "GameState") -> None:
        """Cast a copy of the spell side, unpreparing this creature."""
        if not self.prepared:
            return
        self.prepared = False
        # In a full implementation, this would create and resolve a copy of
        # Venomous Words. Simplified for now.
