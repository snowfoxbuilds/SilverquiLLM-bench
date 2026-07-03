"""Card implementation for Rearing Embermare."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class RearingEmbermare(Creature):
    """Rearing Embermare — {4}{R} — Creature — Horse Beast (4/5).

    Reach, haste.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rearing Embermare")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.REACH | Keyword.HASTE)
        kwargs.setdefault("subtypes", {"Horse", "Beast"})
        super().__init__(**kwargs)
