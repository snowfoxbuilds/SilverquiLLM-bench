from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class TwinflameTyrant(Creature):
    """Twinflame Tyrant."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Twinflame Tyrant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{R}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 5)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon"}
        super().__init__(**kwargs)
