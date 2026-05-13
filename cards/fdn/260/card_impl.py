"""Card implementation for BlossomingSands."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class BlossomingSands(GainLand):
    """Blossoming Sands — ETB tapped, gain 1 life, {T}: Add {G} or {W}."""
    _mana_colors = (ManaType.GREEN, ManaType.WHITE)
    _mana_symbols = ("G", "W")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["BlossomingSands"]
