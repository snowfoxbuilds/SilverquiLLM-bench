from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.types import ManaCost


class ValkyriesCall(Enchantment):
    """Valkyrie's Call."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Valkyrie's Call")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}"))
        super().__init__(**kwargs)
