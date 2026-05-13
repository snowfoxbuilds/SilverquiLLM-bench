from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class HeraldOfEternalDawn(Creature):
    """Herald of Eternal Dawn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Herald of Eternal Dawn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}{W}{W}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.FLASH)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Angel"}
        super().__init__(**kwargs)
