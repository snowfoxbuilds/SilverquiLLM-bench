"""Card implementation for Thornwood Falls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class ThornwoodFalls(GainLand):
    """Thornwood Falls — ETB tapped, gain 1 life, {T}: Add {G} or {U}."""
    _mana_colors = (ManaType.GREEN, ManaType.BLUE)
    _mana_symbols = ("G", "U")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thornwood Falls")
        super().__init__(**kwargs)

