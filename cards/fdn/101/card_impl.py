from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class CacklingProwler(Creature):
    """Cackling Prowler."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cackling Prowler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Hyena", "Rogue"}
        super().__init__(**kwargs)
