from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class FieryAnnihilation(Instant):
    """Fiery Annihilation."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fiery Annihilation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)
