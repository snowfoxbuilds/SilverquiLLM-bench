from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class ArmasaurGuide(Creature):
    """Armasaur Guide."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Armasaur Guide")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dinosaur"}
        super().__init__(**kwargs)
