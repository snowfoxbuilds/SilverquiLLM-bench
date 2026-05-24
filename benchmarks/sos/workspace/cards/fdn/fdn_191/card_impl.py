"""Card implementation for Brazen Scourge."""

from __future__ import annotations
from typing import TYPE_CHECKING

from benchmarks.sos.workspace.engine.creatures import make_vanilla
from benchmarks.sos.workspace.engine.types import Keyword

if TYPE_CHECKING:
    from benchmarks.sos.workspace.cards.registry import CardRegistry

BrazenScourge = make_vanilla(
    "Brazen Scourge", "{1}{R}{R}", 3, 3,
    keywords=Keyword.HASTE,
    creature_types={"Gremlin"},
)
