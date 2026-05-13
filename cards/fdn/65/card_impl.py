from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.types import ManaCost


class MidnightSnack(Enchantment):
    """Midnight Snack."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Midnight Snack")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        super().__init__(**kwargs)
