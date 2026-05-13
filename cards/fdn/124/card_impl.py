from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class PerforatingArtist(Creature):
    """Perforating Artist."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Perforating Artist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{R}"))
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Devil"}
        super().__init__(**kwargs)
