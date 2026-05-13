from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class QuakestriderCeratops(Creature):
    """Quakestrider Ceratops."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quakestrider Ceratops")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}{G}"))
        kwargs.setdefault("base_power", 12)
        kwargs.setdefault("base_toughness", 8)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dinosaur"}
        super().__init__(**kwargs)
