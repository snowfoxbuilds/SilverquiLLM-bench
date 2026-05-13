from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class ExemplarOfLight(Creature):
    """Exemplar of Light."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Exemplar of Light")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{W}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Angel"}
        super().__init__(**kwargs)
