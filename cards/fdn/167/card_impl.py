from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class TolarianTerror(Creature):
    """Tolarian Terror."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tolarian Terror")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{U}"))
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Serpent"}
        super().__init__(**kwargs)
