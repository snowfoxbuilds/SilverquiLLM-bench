from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SwiftbladeVindicator(Creature):
    """Swiftblade Vindicator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swiftblade Vindicator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("keywords", Keyword.VIGILANCE | Keyword.TRAMPLE | Keyword.DOUBLE_STRIKE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Soldier"}
        super().__init__(**kwargs)
