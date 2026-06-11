"""Card implementation for Spellbook Seeker // Careful Study."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class CarefulStudy(Sorcery):
    """Careful Study — {U} — Sorcery (spell side)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Careful Study")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class SpellbookSeeker(Creature):
    """Spellbook Seeker — {3}{U} — 3/3 — Creature — Bird Wizard.

    Flying.
    This creature enters prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spellbook Seeker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("subtypes", {"Bird", "Wizard"})
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Enters prepared."""
        self.is_prepared = True

    def get_spell_side(self) -> CarefulStudy:
        """Return the spell side (Careful Study)."""
        return CarefulStudy(owner=self.owner)

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if the prepared spell can be cast."""
        return self.is_prepared

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of the spell side and unprepare."""
        if not self.is_prepared:
            return
        self.is_prepared = False
