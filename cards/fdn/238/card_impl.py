from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class ConsumingAberration(Creature):
    """Consuming Aberration."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Consuming Aberration")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{B}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Horror"}
        super().__init__(**kwargs)
