from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class SphinxOfForgottenLore(Creature):
    """Sphinx of Forgotten Lore."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sphinx of Forgotten Lore")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.FLASH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Sphinx"}
        super().__init__(**kwargs)
