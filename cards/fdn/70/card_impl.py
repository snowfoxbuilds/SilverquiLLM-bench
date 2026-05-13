from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SoulShackledZombie(Creature):
    """Soul-Shackled Zombie."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soul-Shackled Zombie")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Zombie"}
        super().__init__(**kwargs)
