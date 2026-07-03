"""Card implementation for Pest Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class PestMascot(Creature):
    """Pest Mascot — {1}{B}{G} — 2/3 — Creature — Pest Ape.

    Trample
    Whenever you gain life, put a +1/+1 counter on this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        kwargs.setdefault("subtypes", {"Pest", "Ape"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def on_life_gained(self, game: "GameState", amount: int = 0, **kwargs: Any) -> None:
        """Triggered: whenever you gain life, put a +1/+1 counter on this creature."""
        self.plus_one_counters += 1

    def on_opponent_life_gained(self, game: "GameState", amount: int = 0, **kwargs: Any) -> None:
        """Opponent gaining life does NOT trigger this ability."""
        pass
