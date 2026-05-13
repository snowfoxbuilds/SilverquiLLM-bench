from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class AegisTurtle(Creature):
    """Aegis Turtle."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Aegis Turtle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 5)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Turtle"}
        super().__init__(**kwargs)
