from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class InspiringCall(Instant):
    """Inspiring Call."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inspiring Call")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        super().__init__(**kwargs)
