from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class CracklingCyclops(Creature):
    """Crackling Cyclops."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crackling Cyclops")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Cyclops", "Wizard"}
        super().__init__(**kwargs)
