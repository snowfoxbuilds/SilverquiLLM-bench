from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class VampireNighthawk(Creature):
    """Vampire Nighthawk."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vampire Nighthawk")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH | Keyword.FLYING | Keyword.LIFELINK)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vampire", "Shaman"}
        super().__init__(**kwargs)
