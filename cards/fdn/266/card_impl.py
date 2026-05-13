"""Card implementation for ScouredBarrens."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class ScouredBarrens(GainLand):
    """Scoured Barrens — ETB tapped, gain 1 life, {T}: Add {W} or {B}."""
    _mana_colors = (ManaType.WHITE, ManaType.BLACK)
    _mana_symbols = ("W", "B")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["ScouredBarrens"]
