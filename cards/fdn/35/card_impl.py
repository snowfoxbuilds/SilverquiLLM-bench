from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class DrakeHatcher(Creature):
    """Drake Hatcher."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Drake Hatcher")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("keywords", Keyword.PROWESS | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Wizard"}
        super().__init__(**kwargs)
