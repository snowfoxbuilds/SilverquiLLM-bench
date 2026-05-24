"""Card implementation for Elementalist Adept."""

from __future__ import annotations
from typing import TYPE_CHECKING

from benchmarks.sos.workspace.engine.creatures import make_vanilla
from benchmarks.sos.workspace.engine.types import Keyword

if TYPE_CHECKING:
    from benchmarks.sos.workspace.cards.registry import CardRegistry

ElementalistAdept = make_vanilla(
    "Elementalist Adept", "{1}{U}", 2, 1,
    keywords=Keyword.FLASH,
    creature_types={"Human", "Wizard"},
)
