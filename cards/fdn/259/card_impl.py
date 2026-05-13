"""Card implementation for Bloodfell Caves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class BloodfellCaves(GainLand):
    """Bloodfell Caves — ETB tapped, gain 1 life, {T}: Add {B} or {R}."""
    _mana_colors = (ManaType.BLACK, ManaType.RED)
    _mana_symbols = ("B", "R")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bloodfell Caves")
        super().__init__(**kwargs)

