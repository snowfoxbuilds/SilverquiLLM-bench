"""Card implementation for Serra Angel."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry

SerraAngel = make_vanilla(
    "Serra Angel", "{3}{W}{W}", 4, 4,
    keywords=Keyword.FLYING | Keyword.VIGILANCE,
    creature_types={"Angel"},
)
