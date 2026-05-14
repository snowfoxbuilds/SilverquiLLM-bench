"""Card implementation for Healer's Hawk."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry

HealersHawk = make_vanilla(
    "Healer's Hawk", "{W}", 1, 1,
    keywords=Keyword.FLYING | Keyword.LIFELINK,
    creature_types={"Bird"},
)
