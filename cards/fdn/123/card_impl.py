from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class NivMizzetVisionary(Creature):
    """Niv-Mizzet, Visionary."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Niv-Mizzet, Visionary")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{R}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon", "Wizard"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
