"""Card implementation for TranquilCove."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class TranquilCove(GainLand):
    """Tranquil Cove — ETB tapped, gain 1 life, {T}: Add {W} or {U}."""
    _mana_colors = (ManaType.WHITE, ManaType.BLUE)
    _mana_symbols = ("W", "U")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["TranquilCove"]
