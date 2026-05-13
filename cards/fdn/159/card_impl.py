from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class MockingSprite(Creature):
    """Mocking Sprite."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mocking Sprite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Faerie", "Rogue"}
        super().__init__(**kwargs)
