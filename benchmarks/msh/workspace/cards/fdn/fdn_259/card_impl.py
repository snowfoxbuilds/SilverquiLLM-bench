"""Card implementation for Bloodfell Caves."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

BloodfellCaves = make_gainlife_tapland(
    "Bloodfell Caves", (ManaType.BLACK, ManaType.RED), 259
)
