from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class HidetsugusSecondRite(Instant):
    """Hidetsugu's Second Rite."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hidetsugu's Second Rite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)
