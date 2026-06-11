"""Card implementation for Ulna Alley Shopkeep."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class UlnaAlleyShopkeep(Creature):
    """Ulna Alley Shopkeep — {2}{B} — Creature — Goblin Warlock.

    2/3, Menace.
    Infusion — This creature gets +2/+0 as long as you gained life this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ulna Alley Shopkeep")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("subtypes", {"Goblin", "Warlock"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def get_power(self, game: "GameState | None" = None) -> int:
        """Return power, with +2 if controller gained life this turn."""
        base = super().get_power(game)
        if self.controller and getattr(self.controller, "life_gained_this_turn", 0) > 0:
            return base + 2
        return base

    def get_toughness(self, game: "GameState | None" = None) -> int:
        """Return toughness (unaffected by infusion)."""
        return super().get_toughness(game)
