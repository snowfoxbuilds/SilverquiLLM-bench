from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class TragicBanshee(Creature):
    """Tragic Banshee."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tragic Banshee")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Spirit"}
        super().__init__(**kwargs)
