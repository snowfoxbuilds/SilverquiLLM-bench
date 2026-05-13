"""Card implementation for Tranquil Cove."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class TranquilCove(GainLand):
    """Tranquil Cove — ETB tapped, gain 1 life, {T}: Add {W} or {U}."""
    _mana_colors = (ManaType.WHITE, ManaType.BLUE)
    _mana_symbols = ("W", "U")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tranquil Cove")
        super().__init__(**kwargs)

