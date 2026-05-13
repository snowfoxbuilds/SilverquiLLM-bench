from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class ArchmageOfRunes(Creature):
    """Archmage of Runes."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Archmage of Runes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 6)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Giant", "Wizard"}
        super().__init__(**kwargs)
