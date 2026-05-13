from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class TatyovaBenthicDruid(Creature):
    """Tatyova, Benthic Druid."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tatyova, Benthic Druid")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{U}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Merfolk", "Druid"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
