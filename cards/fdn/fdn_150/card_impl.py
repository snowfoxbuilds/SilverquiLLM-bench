"""Card implementation for Aegis Turtle."""

from __future__ import annotations
from typing import TYPE_CHECKING

from benchmarks.sos.workspace.engine.creatures import make_vanilla

if TYPE_CHECKING:
    from cards.registry import CardRegistry

AegisTurtle = make_vanilla(
    "Aegis Turtle", "{U}", 0, 5,
    creature_types={"Turtle"},
)
