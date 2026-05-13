from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class CryptFeaster(Creature):
    """Crypt Feaster."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crypt Feaster")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Zombie"}
        super().__init__(**kwargs)
