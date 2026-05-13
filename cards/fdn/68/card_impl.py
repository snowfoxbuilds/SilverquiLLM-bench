from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SanguineSyphoner(Creature):
    """Sanguine Syphoner."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sanguine Syphoner")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vampire", "Warlock"}
        super().__init__(**kwargs)
