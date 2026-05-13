from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class ClinquantSkymage(Creature):
    """Clinquant Skymage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Clinquant Skymage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Bird", "Wizard"}
        super().__init__(**kwargs)
