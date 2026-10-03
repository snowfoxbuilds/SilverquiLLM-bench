"""Card implementation for Quakestrider Ceratops."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla

if TYPE_CHECKING:
    from cards.registry import CardRegistry

QuakestriderCeratops = make_vanilla(
    "Quakestrider Ceratops", "{3}{G}{G}{G}", 12, 8,
    creature_types={"Dinosaur"},
)
