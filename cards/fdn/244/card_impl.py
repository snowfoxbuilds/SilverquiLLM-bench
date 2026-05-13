from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class Progenitus(Creature):
    """Progenitus."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Progenitus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}"))
        kwargs.setdefault("base_power", 10)
        kwargs.setdefault("base_toughness", 10)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Hydra", "Avatar"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
