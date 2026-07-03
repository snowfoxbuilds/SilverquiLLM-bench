"""Card implementation for Infirmary Healer // Stream of Life."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class InfirmaryHealerStreamOfLife(Creature):
    """Infirmary Healer // Stream of Life — {1}{G} — Creature — Cat Cleric (2/3).

    This creature enters prepared.
    While prepared, you may cast a copy of Stream of Life ({X}{G} sorcery:
    You gain X life). Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Infirmary Healer // Stream of Life")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_enter_battlefield(self, game: "GameState") -> None:
        """This creature enters prepared."""
        self.is_prepared = True

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if prepared spell can be cast."""
        return self.is_prepared

    def cast_prepared_spell(self, game: "GameState", x_value: int = 0) -> None:
        """Cast a copy of Stream of Life: gain X life, then unprepare."""
        if not self.is_prepared:
            return
        controller = self.controller
        controller.life += x_value
        self.is_prepared = False
