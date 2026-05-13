from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class ThrillOfPossibility(Instant):
    """Thrill of Possibility."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thrill of Possibility")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)
