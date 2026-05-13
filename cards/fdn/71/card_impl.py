from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class Stab(Instant):
    """Stab."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stab")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)
