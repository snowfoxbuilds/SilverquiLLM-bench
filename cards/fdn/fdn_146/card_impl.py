"""Card implementation for Savannah Lions."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla

if TYPE_CHECKING:
    from cards.registry import CardRegistry

SavannahLions = make_vanilla(
    "Savannah Lions", "{W}", 2, 1,
    creature_types={"Cat"},
)
