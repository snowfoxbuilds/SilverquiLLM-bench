"""Card implementation for Jungle Hollow."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

JungleHollow = make_gainlife_tapland(
    "Jungle Hollow", (ManaType.BLACK, ManaType.GREEN), 263
)
