from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SpitfireLagac(Creature):
    """Spitfire Lagac."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spitfire Lagac")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Lizard"}
        super().__init__(**kwargs)
