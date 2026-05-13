from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class UnchartedVoyage(Instant):
    """Uncharted Voyage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Uncharted Voyage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        super().__init__(**kwargs)
