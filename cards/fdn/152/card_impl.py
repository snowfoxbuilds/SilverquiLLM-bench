from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class BrinebornCutthroat(Creature):
    """Brineborn Cutthroat."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brineborn Cutthroat")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Merfolk", "Pirate"}
        super().__init__(**kwargs)
