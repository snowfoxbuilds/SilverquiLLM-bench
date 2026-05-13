from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class NeedletoothPack(Creature):
    """Needletooth Pack."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Needletooth Pack")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 5)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dinosaur"}
        super().__init__(**kwargs)
