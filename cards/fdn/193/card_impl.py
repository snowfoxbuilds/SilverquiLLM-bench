from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class DrakusethMawOfFlames(Creature):
    """Drakuseth, Maw of Flames."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Drakuseth, Maw of Flames")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{R}{R}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
