from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SavannahLions(Creature):
    """Savannah Lions."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Savannah Lions")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Cat"}
        super().__init__(**kwargs)
