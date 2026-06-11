"""Card implementation for Maelstrom Artisan // Rocket Volley."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class MaelstromArtisan(Creature):
    """Maelstrom Artisan — {1}{R}{R} — Creature — Minotaur Sorcerer 3/2.

    Haste
    This creature enters prepared. While it's prepared, you may cast a copy
    of its spell (Rocket Volley). Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Maelstrom Artisan")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}{R}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("subtypes", {"Minotaur", "Sorcerer"})
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Enter prepared."""
        self.is_prepared = True

    def cast_prepared_spell(self, game: "GameState", *args: Any) -> None:
        """Cast a copy of Rocket Volley. Unprepares this creature."""
        if not self.is_prepared:
            raise RuntimeError("Cannot cast prepared spell — creature is not prepared")
        self.is_prepared = False
        # The copy of Rocket Volley would deal damage, but for now we just
        # mark the unprepare action as complete.
