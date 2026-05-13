from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment
from engine.types import ManaCost


class ExtravagantReplication(Enchantment):
    """Extravagant Replication."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Extravagant Replication")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        super().__init__(**kwargs)
