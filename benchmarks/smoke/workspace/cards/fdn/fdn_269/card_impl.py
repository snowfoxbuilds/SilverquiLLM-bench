"""Card implementation for Thornwood Falls."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

ThornwoodFalls = make_gainlife_tapland(
    "Thornwood Falls", (ManaType.GREEN, ManaType.BLUE), 269
)
