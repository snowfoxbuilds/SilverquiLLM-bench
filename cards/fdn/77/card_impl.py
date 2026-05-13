from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class ZulAshurLichLord(Creature):
    """Zul Ashur, Lich Lord."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zul Ashur, Lich Lord")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Zombie", "Warlock"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
