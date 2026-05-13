from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class BloodthirstyConqueror(Creature):
    """Bloodthirsty Conqueror."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bloodthirsty Conqueror")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH | Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vampire", "Knight"}
        super().__init__(**kwargs)
