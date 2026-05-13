from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class KellanPlanarTrailblazer(Creature):
    """Kellan, Planar Trailblazer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kellan, Planar Trailblazer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Faerie", "Scout"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
