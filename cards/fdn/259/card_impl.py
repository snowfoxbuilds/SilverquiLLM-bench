"""Card implementation for BloodfellCaves."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class BloodfellCaves(GainLand):
    """Bloodfell Caves — ETB tapped, gain 1 life, {T}: Add {B} or {R}."""
    _mana_colors = (ManaType.BLACK, ManaType.RED)
    _mana_symbols = ("B", "R")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["BloodfellCaves"]
