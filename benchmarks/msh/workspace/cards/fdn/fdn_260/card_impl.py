"""Card implementation for Blossoming Sands."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

BlossomingSands = make_gainlife_tapland(
    "Blossoming Sands", (ManaType.GREEN, ManaType.WHITE), 260
)
