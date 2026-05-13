from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SlumberingCerberus(Creature):
    """Slumbering Cerberus."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Slumbering Cerberus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dog"}
        super().__init__(**kwargs)
