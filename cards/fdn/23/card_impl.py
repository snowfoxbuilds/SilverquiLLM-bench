from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SkyknightSquire(Creature):
    """Skyknight Squire."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Skyknight Squire")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Cat", "Scout"}
        super().__init__(**kwargs)
