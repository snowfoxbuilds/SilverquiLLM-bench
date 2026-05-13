from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SerraAngel(Creature):
    """Serra Angel."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Serra Angel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Angel"}
        super().__init__(**kwargs)
