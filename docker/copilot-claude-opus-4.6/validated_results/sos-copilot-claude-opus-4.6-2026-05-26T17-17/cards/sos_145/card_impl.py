"""Card implementation for Emeritus of Abundance // Regrowth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfAbundanceRegrowth(Creature):
    """Emeritus of Abundance // Regrowth — {2}{G} — Creature — Elf Druid — 3/4.

    Vigilance
    This creature enters prepared.
    Whenever this creature attacks, if you control eight or more lands,
    this creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Abundance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.VIGILANCE | Keyword.PREPARED)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        super().__init__(**kwargs)
        self.is_prepared: bool = True

    def on_attack(self, game: "GameState") -> None:
        """Attack trigger: if controlling 8+ lands, become prepared."""
        controller = self.controller
        if controller is None:
            return
        bf = game.get_battlefield(controller)
        land_count = sum(
            1 for obj in bf.get_all()
            if CardType.LAND in getattr(obj, "card_types", set())
        )
        if land_count >= 8:
            self.is_prepared = True
