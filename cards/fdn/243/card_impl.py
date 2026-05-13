from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class MuldrothaTheGravetide(Creature):
    """Muldrotha, the Gravetide."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muldrotha, the Gravetide")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{G}{U}"))
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elemental", "Avatar"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
