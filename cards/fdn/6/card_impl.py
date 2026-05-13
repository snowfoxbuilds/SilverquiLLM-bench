from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class ClawsOut(Instant):
    """Claws Out."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Claws Out")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}"))
        super().__init__(**kwargs)
