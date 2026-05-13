from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class AbyssalHarvester(Creature):
    """Abyssal Harvester."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abyssal Harvester")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Demon", "Warlock"}
        super().__init__(**kwargs)
