from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class CatCollector(Creature):
    """Cat Collector."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cat Collector")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Citizen"}
        super().__init__(**kwargs)
