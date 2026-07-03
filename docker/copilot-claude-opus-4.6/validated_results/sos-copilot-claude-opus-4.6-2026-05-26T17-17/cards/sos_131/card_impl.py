"""Card implementation for Strife Scholar // Awaken the Ages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class StrifeScholar(Creature):
    """Strife Scholar — {2}{R} — Creature — Orc Sorcerer — 3/2.

    Ward—Pay 2 life.
    This creature enters prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Strife Scholar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.WARD | Keyword.PREPARED)
        kwargs.setdefault("subtypes", {"Orc", "Sorcerer"})
        kwargs.setdefault(
            "rules_text",
            "Ward—Pay 2 life.\nThis creature enters prepared.",
        )
        super().__init__(**kwargs)
        self.ward_cost: int = 2
        self.prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """When this creature enters the battlefield, it enters prepared."""
        self.prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the prepared spell copy (Awaken the Ages). Unprepares the creature."""
        self.prepared = False


# Keep backward compat alias
StrifeScholarAwakenTheAges = StrifeScholar

