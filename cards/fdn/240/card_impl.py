from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class GoodFortuneUnicorn(Creature):
    """Good-Fortune Unicorn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Good-Fortune Unicorn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{W}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Unicorn"}
        super().__init__(**kwargs)
