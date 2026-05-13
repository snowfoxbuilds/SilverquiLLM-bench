from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class ElendaSaintOfDusk(Creature):
    """Elenda, Saint of Dusk."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elenda, Saint of Dusk")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("keywords", Keyword.LIFELINK | Keyword.HEXPROOF)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vampire", "Knight"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
