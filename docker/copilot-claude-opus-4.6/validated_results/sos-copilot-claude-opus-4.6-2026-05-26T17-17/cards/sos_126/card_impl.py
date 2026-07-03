"""Card implementation for Pigment Wrangler // Striking Palette."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class PigmentWrangler(Creature):
    """Pigment Wrangler — {4}{R} — Creature — Orc Sorcerer (4/4).

    Flying. This creature enters prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pigment Wrangler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("subtypes", {"Orc", "Sorcerer"})
        super().__init__(**kwargs)
        self.prepared: bool = True
        self.colors: set[str] = {"R"}

    def use_prepared_ability(self, game: "GameState") -> None:
        """Cast a copy of the spell side, unpreparing the creature."""
        self.prepared = False
