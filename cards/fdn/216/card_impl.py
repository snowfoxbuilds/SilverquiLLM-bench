from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.types import ManaCost


class DoublingSeason(Enchantment):
    """Doubling Season."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Doubling Season")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}"))
        super().__init__(**kwargs)
