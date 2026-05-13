from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class VanguardSeraph(Creature):
    """Vanguard Seraph."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vanguard Seraph")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Angel", "Warrior"}
        super().__init__(**kwargs)
