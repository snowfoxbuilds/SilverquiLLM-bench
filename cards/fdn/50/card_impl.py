from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SkyshipBuccaneer(Creature):
    """Skyship Buccaneer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Skyship Buccaneer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Pirate"}
        super().__init__(**kwargs)
