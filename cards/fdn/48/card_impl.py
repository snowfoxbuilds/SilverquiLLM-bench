from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class Refute(Instant):
    """Refute."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Refute")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        super().__init__(**kwargs)
