from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class CuratorOfDestinies(Creature):
    """Curator of Destinies."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Curator of Destinies")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Sphinx"}
        super().__init__(**kwargs)
