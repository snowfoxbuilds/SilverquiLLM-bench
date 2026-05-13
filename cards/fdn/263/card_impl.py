"""Card implementation for JungleHollow."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class JungleHollow(GainLand):
    """Jungle Hollow — ETB tapped, gain 1 life, {T}: Add {B} or {G}."""
    _mana_colors = (ManaType.BLACK, ManaType.GREEN)
    _mana_symbols = ("B", "G")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["JungleHollow"]
