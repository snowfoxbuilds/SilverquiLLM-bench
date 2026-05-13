from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class ArahboTheFirstFang(Creature):
    """Arahbo, the First Fang."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arahbo, the First Fang")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Cat", "Avatar"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
