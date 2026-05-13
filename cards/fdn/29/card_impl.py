from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class ArcaneEpiphany(Instant):
    """Arcane Epiphany."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arcane Epiphany")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        super().__init__(**kwargs)
