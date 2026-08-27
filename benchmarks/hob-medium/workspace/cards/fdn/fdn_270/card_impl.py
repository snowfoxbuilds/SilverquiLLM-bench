"""Card implementation for Tranquil Cove."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

TranquilCove = make_gainlife_tapland(
    "Tranquil Cove", (ManaType.WHITE, ManaType.BLUE), 270
)
