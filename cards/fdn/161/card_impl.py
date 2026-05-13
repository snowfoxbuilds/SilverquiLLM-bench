from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.types import ManaCost


class Omniscience(Enchantment):
    """Omniscience."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Omniscience")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}{U}{U}{U}"))
        super().__init__(**kwargs)
