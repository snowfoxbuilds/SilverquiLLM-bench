"""Card implementation for Dismal Backwater."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cards.fdn.utils import GainLand
from engine.types import ManaType


class DismalBackwater(GainLand):
    """Dismal Backwater — ETB tapped, gain 1 life, {T}: Add {U} or {B}."""
    _mana_colors = (ManaType.BLUE, ManaType.BLACK)
    _mana_symbols = ("U", "B")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dismal Backwater")
        super().__init__(**kwargs)

