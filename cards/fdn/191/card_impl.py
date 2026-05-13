from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class BrazenScourge(Creature):
    """Brazen Scourge."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brazen Scourge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}{R}"))
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Gremlin"}
        super().__init__(**kwargs)
