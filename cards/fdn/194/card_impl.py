from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class EtaliPrimalStorm(Creature):
    """Etali, Primal Storm."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Etali, Primal Storm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{R}"))
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dinosaur"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
