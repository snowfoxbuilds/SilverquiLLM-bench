from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SearslicerGoblin(Creature):
    """Searslicer Goblin."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Searslicer Goblin")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Goblin", "Warrior"}
        super().__init__(**kwargs)
