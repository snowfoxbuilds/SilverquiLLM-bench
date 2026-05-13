from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class DwynensElite(Creature):
    """Dwynen's Elite."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dwynen's Elite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elf", "Warrior"}
        super().__init__(**kwargs)
