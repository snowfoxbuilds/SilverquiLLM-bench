"""Card implementation for Skycoach Conductor // All Aboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class AllAboard(Instant):
    """All Aboard — {U} — Instant (spell side)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "All Aboard")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class SkycoachConductor(Creature):
    """Skycoach Conductor — {2}{U} — 2/3 — Creature — Bird Pilot.

    Flash, Flying, Vigilance.
    This creature enters prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Skycoach Conductor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("subtypes", {"Bird", "Pilot"})
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Enters prepared."""
        self.is_prepared = True

    def get_spell_side(self) -> AllAboard:
        """Return the spell side (All Aboard)."""
        return AllAboard(owner=self.owner)

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if the prepared spell can be cast."""
        return self.is_prepared

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of the spell side and unprepare."""
        if not self.is_prepared:
            return
        self.is_prepared = False
