from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class LightshellDuo(Creature):
    """Lightshell Duo."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lightshell Duo")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("keywords", Keyword.PROWESS)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Rat", "Otter"}
        super().__init__(**kwargs)
