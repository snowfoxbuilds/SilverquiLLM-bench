from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class BalmorBattlemageCaptain(Creature):
    """Balmor, Battlemage Captain."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Balmor, Battlemage Captain")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}{R}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Bird", "Wizard"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
