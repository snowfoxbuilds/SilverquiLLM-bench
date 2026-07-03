"""Card implementation for Blazing Firesinger // Seething Song."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class BlazingFiresinger(Creature):
    """Blazing Firesinger — {2}{R} — 2/3 Creature — Dwarf Bard.

    This creature enters prepared. (While it's prepared, you may cast a copy
    of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blazing Firesinger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Bard"})
        kwargs.setdefault("keywords", Keyword.PREPARED)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.prepared: bool = False
        self.spell_name: str = "Seething Song"

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Enter prepared."""
        self.prepared = True

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if the prepared spell can be cast."""
        return self.prepared is True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of the spell side, unpreparing this creature."""
        if not self.prepared:
            return
        self.prepared = False
