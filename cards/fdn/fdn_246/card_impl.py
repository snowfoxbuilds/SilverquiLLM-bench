"""Card implementation for Swiftblade Vindicator."""

from __future__ import annotations
from typing import TYPE_CHECKING

from benchmarks.sos.workspace.engine.creatures import make_vanilla
from benchmarks.sos.workspace.engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry

SwiftbladeVindicator = make_vanilla(
    "Swiftblade Vindicator", "{R}{W}", 1, 1,
    keywords=Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE | Keyword.TRAMPLE,
    creature_types={"Human", "Soldier"},
)
