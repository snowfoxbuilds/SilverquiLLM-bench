from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class FirebrandArcher(Creature):
    """Firebrand Archer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Firebrand Archer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Archer"}
        super().__init__(**kwargs)
