"""Card implementation for Healer's Hawk."""

from __future__ import annotations
from typing import TYPE_CHECKING

from benchmarks.sos.workspace.engine.creatures import make_vanilla
from benchmarks.sos.workspace.engine.types import Keyword

if TYPE_CHECKING:
    from benchmarks.sos.workspace.cards.registry import CardRegistry

HealersHawk = make_vanilla(
    "Healer's Hawk", "{W}", 1, 1,
    keywords=Keyword.FLYING | Keyword.LIFELINK,
    creature_types={"Bird"},
)
