"""Card implementation for Studious First-Year // Rampant Growth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class RampantGrowthSpell(Sorcery):
    """A copy of Rampant Growth spell."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rampant Growth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)


class StudiousFirstYearRampantGrowth(Creature):
    """Studious First-Year // Rampant Growth — {G} — 1/1 — Bear Wizard.

    This creature enters prepared. (While it's prepared, you may cast a copy
    of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Studious First-Year // Rampant Growth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Bear", "Wizard"})
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def enter_battlefield(self, game: "GameState") -> None:
        """Enter the battlefield prepared."""
        self.is_prepared = True

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if the prepared spell can be cast."""
        return self.is_prepared

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Rampant Growth, unpreparing this creature."""
        if not self.is_prepared:
            return
        self.is_prepared = False

    def get_prepared_spell(self, game: "GameState") -> "RampantGrowthSpell":
        """Return a copy of the prepared spell (Rampant Growth)."""
        return RampantGrowthSpell(owner=self.controller, controller=self.controller)
