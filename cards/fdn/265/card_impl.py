"""Card implementation for RuggedHighlands."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class RuggedHighlands(GainLand):
    """Rugged Highlands — ETB tapped, gain 1 life, {T}: Add {R} or {G}."""
    _mana_colors = (ManaType.RED, ManaType.GREEN)
    _mana_symbols = ("R", "G")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["RuggedHighlands"]
