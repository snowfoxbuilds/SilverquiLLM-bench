from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class ElementalistAdept(Creature):
    """Elementalist Adept."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elementalist Adept")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("keywords", Keyword.PROWESS | Keyword.FLASH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Wizard"}
        super().__init__(**kwargs)
