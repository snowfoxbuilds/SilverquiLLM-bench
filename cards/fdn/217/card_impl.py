from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class DwynenGiltLeafDaen(Creature):
    """Dwynen, Gilt-Leaf Daen."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dwynen, Gilt-Leaf Daen")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{G}"))
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elf", "Warrior"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
