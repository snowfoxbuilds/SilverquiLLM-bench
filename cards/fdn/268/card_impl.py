"""Card implementation for SwiftwaterCliffs."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class SwiftwaterCliffs(GainLand):
    """Swiftwater Cliffs — ETB tapped, gain 1 life, {T}: Add {U} or {R}."""
    _mana_colors = (ManaType.BLUE, ManaType.RED)
    _mana_symbols = ("U", "R")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["SwiftwaterCliffs"]
