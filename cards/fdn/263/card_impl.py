"""Card implementation for Jungle Hollow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class JungleHollow(GainLand):
    """Jungle Hollow — ETB tapped, gain 1 life, {T}: Add {B} or {G}."""
    _mana_colors = (ManaType.BLACK, ManaType.GREEN)
    _mana_symbols = ("B", "G")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Jungle Hollow")
        super().__init__(**kwargs)

