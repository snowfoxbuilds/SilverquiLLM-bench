"""Card implementation for Adventurous Eater // Have a Bite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class AdventurousEater(Creature):
    """Adventurous Eater — {2}{B} — Creature — Human Warlock.

    This creature enters prepared. (While it's prepared, you may cast a
    copy of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Adventurous Eater")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.PREPARED)
        kwargs.setdefault("subtypes", {"Human", "Warlock"})
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_enter_battlefield(self, game: "GameState") -> None:
        """This creature enters prepared."""
        self.prepared = True

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if the prepared spell can be cast."""
        return self.prepared is True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of the spell side, unpreparing the creature."""
        if not self.prepared:
            return
        self.prepared = False
