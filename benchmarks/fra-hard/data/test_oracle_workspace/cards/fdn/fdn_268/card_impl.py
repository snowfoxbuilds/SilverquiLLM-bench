"""Card implementation for Swiftwater Cliffs."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

SwiftwaterCliffs = make_gainlife_tapland(
    "Swiftwater Cliffs", (ManaType.BLUE, ManaType.RED), 268
)
