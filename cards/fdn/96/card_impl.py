from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class StrongboxRaider(Creature):
    """Strongbox Raider."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Strongbox Raider")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{R}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Orc", "Pirate"}
        super().__init__(**kwargs)
