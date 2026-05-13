from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class WildwoodScourge(Creature):
    """Wildwood Scourge."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wildwood Scourge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Hydra"}
        super().__init__(**kwargs)
