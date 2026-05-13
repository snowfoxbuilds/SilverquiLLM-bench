from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class RuneScarredDemon(Creature):
    """Rune-Scarred Demon."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rune-Scarred Demon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}{B}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Demon"}
        super().__init__(**kwargs)
