from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class EagerTrufflesnout(Creature):
    """Eager Trufflesnout."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Eager Trufflesnout")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Boar"}
        super().__init__(**kwargs)
