from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class GhaltaPrimalHunger(Creature):
    """Ghalta, Primal Hunger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ghalta, Primal Hunger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}{G}{G}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 12)
        kwargs.setdefault("base_toughness", 12)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dinosaur"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
