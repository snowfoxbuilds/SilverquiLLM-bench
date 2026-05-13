"""Card implementation for Blossoming Sands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class BlossomingSands(GainLand):
    """Blossoming Sands — ETB tapped, gain 1 life, {T}: Add {G} or {W}."""
    _mana_colors = (ManaType.GREEN, ManaType.WHITE)
    _mana_symbols = ("G", "W")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blossoming Sands")
        super().__init__(**kwargs)

