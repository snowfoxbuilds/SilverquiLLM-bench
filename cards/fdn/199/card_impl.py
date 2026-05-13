from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class FrenziedGoblin(Creature):
    """Frenzied Goblin."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Frenzied Goblin")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Goblin", "Berserker"}
        super().__init__(**kwargs)
