from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SquadRallier(Creature):
    """Squad Rallier."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Squad Rallier")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Scout"}
        super().__init__(**kwargs)
