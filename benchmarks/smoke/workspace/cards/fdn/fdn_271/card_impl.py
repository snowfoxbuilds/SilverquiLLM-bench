"""Card implementation for Wind-Scarred Crag."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

WindScarredCrag = make_gainlife_tapland(
    "Wind-Scarred Crag", (ManaType.RED, ManaType.WHITE), 271
)
