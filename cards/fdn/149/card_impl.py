from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class YouthfulValkyrie(Creature):
    """Youthful Valkyrie."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Youthful Valkyrie")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Angel"}
        super().__init__(**kwargs)
