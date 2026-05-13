"""Card implementation for DismalBackwater."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType


from cards.fdn._land_bases import TapLand, GainLand, _tap_cost


class DismalBackwater(GainLand):
    """Dismal Backwater — ETB tapped, gain 1 life, {T}: Add {U} or {B}."""
    _mana_colors = (ManaType.BLUE, ManaType.BLACK)
    _mana_symbols = ("U", "B")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)



__all__ = ["DismalBackwater"]
