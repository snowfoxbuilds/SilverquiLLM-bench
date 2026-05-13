from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class AshrootAnimist(Creature):
    """Ashroot Animist."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ashroot Animist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{G}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Lizard", "Druid"}
        super().__init__(**kwargs)
