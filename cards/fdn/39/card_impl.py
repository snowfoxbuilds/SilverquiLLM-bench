from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class GrapplingKraken(Creature):
    """Grappling Kraken."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grappling Kraken")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 6)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Kraken"}
        super().__init__(**kwargs)
