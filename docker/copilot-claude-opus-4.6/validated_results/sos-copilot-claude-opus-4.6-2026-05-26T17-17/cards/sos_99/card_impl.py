"""Card implementation for Scheming Silvertongue // Sign in Blood."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SchemingSilvertongue(Creature):
    """Scheming Silvertongue — {1}{B} — Creature — Vampire Warlock 1/3.

    Flying, lifelink.
    At the beginning of your second main phase, if you gained 2 or more life
    this turn, this creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scheming Silvertongue")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.LIFELINK)
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_phase_trigger(self, game: "GameState", phase: str) -> None:
        """Trigger at second main phase if 2+ life gained this turn."""
        if phase == "second_main":
            life_gained = getattr(game, "life_gained_this_turn", {})
            gained = life_gained.get(self.controller, 0)
            if gained >= 2:
                self.prepared = True

    def can_cast_spell_copy(self, game: "GameState") -> bool:
        """Return whether a spell copy can be cast (must be prepared)."""
        return self.prepared

    def cast_spell_copy(self, game: "GameState") -> None:
        """Cast a copy of Sign in Blood, unpreparing this creature."""
        if not self.prepared:
            return
        self.prepared = False
