from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class HighFaeTrickster(Creature):
    """High Fae Trickster."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "High Fae Trickster")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.FLASH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Faerie", "Wizard"}
        super().__init__(**kwargs)
