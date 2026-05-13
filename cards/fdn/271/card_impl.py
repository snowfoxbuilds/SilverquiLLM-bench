"""Card implementation for Wind-Scarred Crag."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class WindScarredCrag(GainLand):
    """Wind-Scarred Crag — ETB tapped, gain 1 life, {T}: Add {R} or {W}."""
    _mana_colors = (ManaType.RED, ManaType.WHITE)
    _mana_symbols = ("R", "W")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wind-Scarred Crag")
        super().__init__(**kwargs)

