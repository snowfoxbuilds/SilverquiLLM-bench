from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class WardensOfTheCycle(Creature):
    """Wardens of the Cycle."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wardens of the Cycle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}{G}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elf", "Warlock"}
        super().__init__(**kwargs)
