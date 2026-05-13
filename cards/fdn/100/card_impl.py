from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class BeastKinRanger(Creature):
    """Beast-Kin Ranger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Beast-Kin Ranger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elf", "Ranger"}
        super().__init__(**kwargs)
