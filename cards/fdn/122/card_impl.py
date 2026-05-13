from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class KykarZephyrAwakener(Creature):
    """Kykar, Zephyr Awakener."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kykar, Zephyr Awakener")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Bird", "Wizard"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
