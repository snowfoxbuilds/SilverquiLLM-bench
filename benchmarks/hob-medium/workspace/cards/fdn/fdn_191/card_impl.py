"""Card implementation for Brazen Scourge."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry

BrazenScourge = make_vanilla(
    "Brazen Scourge", "{1}{R}{R}", 3, 3,
    keywords=Keyword.HASTE,
    creature_types={"Gremlin"},
)
