from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class TimeStop(Instant):
    """Time Stop."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Time Stop")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        super().__init__(**kwargs)
