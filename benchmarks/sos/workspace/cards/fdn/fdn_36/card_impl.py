"""Card implementation for Elementalist Adept."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry

ElementalistAdept = make_vanilla(
    "Elementalist Adept", "{1}{U}", 2, 1,
    keywords=Keyword.FLASH,
    creature_types={"Human", "Wizard"},
)
