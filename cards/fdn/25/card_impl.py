from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SunBlessedHealer(Creature):
    """Sun-Blessed Healer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sun-Blessed Healer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Cleric"}
        super().__init__(**kwargs)
