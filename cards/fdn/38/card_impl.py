from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class FaebloomTrick(Instant):
    """Faebloom Trick."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Faebloom Trick")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        super().__init__(**kwargs)
