from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SireOfSevenDeaths(Creature):
    """Sire of Seven Deaths."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sire of Seven Deaths")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("keywords", Keyword.LIFELINK | Keyword.REACH | Keyword.VIGILANCE | Keyword.FIRST_STRIKE | Keyword.TRAMPLE | Keyword.MENACE | Keyword.WARD)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Eldrazi"}
        super().__init__(**kwargs)
