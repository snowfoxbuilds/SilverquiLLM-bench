from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.types import ManaCost


class ThousandYearStorm(Enchantment):
    """Thousand-Year Storm."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thousand-Year Storm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{R}"))
        super().__init__(**kwargs)
