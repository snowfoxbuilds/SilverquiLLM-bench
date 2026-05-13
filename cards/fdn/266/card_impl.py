"""Card implementation for Scoured Barrens."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class ScouredBarrens(GainLand):
    """Scoured Barrens — ETB tapped, gain 1 life, {T}: Add {W} or {B}."""
    _mana_colors = (ManaType.WHITE, ManaType.BLACK)
    _mana_symbols = ("W", "B")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scoured Barrens")
        super().__init__(**kwargs)

