from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.types import ManaCost


class SylvanScavenging(Enchantment):
    """Sylvan Scavenging."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sylvan Scavenging")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{G}"))
        super().__init__(**kwargs)
