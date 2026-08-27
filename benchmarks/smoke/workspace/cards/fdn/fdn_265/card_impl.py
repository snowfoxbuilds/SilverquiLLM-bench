"""Card implementation for Rugged Highlands."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

RuggedHighlands = make_gainlife_tapland(
    "Rugged Highlands", (ManaType.RED, ManaType.GREEN), 265
)
