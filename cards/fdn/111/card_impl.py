from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class QuilledGreatwurm(Creature):
    """Quilled Greatwurm."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quilled Greatwurm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{G}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Wurm"}
        super().__init__(**kwargs)
