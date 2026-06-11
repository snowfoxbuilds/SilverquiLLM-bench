"""Card implementation for Landscape Painter // Vibrant Idea."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class LandscapePainterVibrantIdea(Creature):
    """Landscape Painter // Vibrant Idea — {1}{U} // {4}{U}.

    Creature — Merfolk Wizard — 2/1.
    This creature enters prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Landscape Painter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Wizard"})
        kwargs.setdefault("keywords", Keyword.PREPARED)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)
        self.prepared: bool = True
        self.spell_mana_cost: ManaCost = ManaCost.parse("{4}{U}")

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Vibrant Idea, unpreparing this creature."""
        self.prepared = False
