from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class GorehornRaider(Creature):
    """Gorehorn Raider."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gorehorn Raider")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Minotaur", "Pirate"}
        super().__init__(**kwargs)
