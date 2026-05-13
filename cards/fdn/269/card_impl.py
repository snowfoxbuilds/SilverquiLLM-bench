"""Card implementation for ThornwoodFalls."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class ThornwoodFalls(GainLand):
    """Thornwood Falls — ETB tapped, gain 1 life, {T}: Add {G} or {U}."""
    _mana_colors = (ManaType.GREEN, ManaType.BLUE)
    _mana_symbols = ("G", "U")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["ThornwoodFalls"]
