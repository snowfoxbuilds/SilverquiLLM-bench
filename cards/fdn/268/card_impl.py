"""Card implementation for Swiftwater Cliffs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class SwiftwaterCliffs(GainLand):
    """Swiftwater Cliffs — ETB tapped, gain 1 life, {T}: Add {U} or {R}."""
    _mana_colors = (ManaType.BLUE, ManaType.RED)
    _mana_symbols = ("U", "R")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swiftwater Cliffs")
        super().__init__(**kwargs)

