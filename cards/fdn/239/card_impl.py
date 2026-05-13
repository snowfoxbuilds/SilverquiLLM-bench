from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class EmpyreanEagle(Creature):
    """Empyrean Eagle."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Empyrean Eagle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Bird", "Spirit"}
        super().__init__(**kwargs)
