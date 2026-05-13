from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class AleshaWhoLaughsAtFate(Creature):
    """Alesha, Who Laughs at Fate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Alesha, Who Laughs at Fate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{R}"))
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Warrior"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
