from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class HealersHawk(Creature):
    """Healer's Hawk."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Healer's Hawk")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.LIFELINK)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Bird"}
        super().__init__(**kwargs)
