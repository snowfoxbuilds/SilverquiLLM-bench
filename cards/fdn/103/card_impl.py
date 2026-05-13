from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class ElfswornGiant(Creature):
    """Elfsworn Giant."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elfsworn Giant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Giant"}
        super().__init__(**kwargs)
