from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class AffectionateIndrik(Creature):
    """Affectionate Indrik."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Affectionate Indrik")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Beast"}
        super().__init__(**kwargs)
