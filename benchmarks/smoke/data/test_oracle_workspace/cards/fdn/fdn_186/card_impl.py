"""Card implementation for Vampire Nighthawk."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry

VampireNighthawk = make_vanilla(
    "Vampire Nighthawk", "{1}{B}{B}", 2, 3,
    keywords=Keyword.FLYING | Keyword.DEATHTOUCH | Keyword.LIFELINK,
    creature_types={"Vampire", "Shaman"},
)
