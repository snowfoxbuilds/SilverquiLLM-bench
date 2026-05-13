"""Card implementation for Rugged Highlands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class RuggedHighlands(GainLand):
    """Rugged Highlands — ETB tapped, gain 1 life, {T}: Add {R} or {G}."""
    _mana_colors = (ManaType.RED, ManaType.GREEN)
    _mana_symbols = ("R", "G")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rugged Highlands")
        super().__init__(**kwargs)

