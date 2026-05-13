from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class HomunculusHorde(Creature):
    """Homunculus Horde."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Homunculus Horde")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Homunculus"}
        super().__init__(**kwargs)
