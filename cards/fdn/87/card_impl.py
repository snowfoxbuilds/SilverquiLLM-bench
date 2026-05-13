from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class GoblinBoarders(Creature):
    """Goblin Boarders."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Boarders")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Goblin", "Pirate"}
        super().__init__(**kwargs)
