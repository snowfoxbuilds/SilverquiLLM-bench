"""Card implementation for Goblin Glasswright // Craft with Pride."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GoblinGlasswright(Creature):
    """Goblin Glasswright — {1}{R} — 2/2 Creature — Goblin Sorcerer.

    This creature enters prepared. While it's prepared, you may cast a copy
    of its spell. Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Glasswright")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.PREPARED)
        super().__init__(**kwargs)
        self.prepared: bool = False
        self.spell_name: str = "Craft with Pride"

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Enter prepared."""
        self.prepared = True

    def cast_prepared_spell(self, game: "GameState", *args: Any) -> None:
        """Cast a copy of the spell side (Craft with Pride). Unprepares this creature."""
        if not self.prepared:
            raise Exception("Cannot cast prepared spell: creature is not prepared.")
        self.prepared = False

