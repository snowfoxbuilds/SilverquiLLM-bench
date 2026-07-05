"""Card implementation for Dismal Backwater."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

DismalBackwater = make_gainlife_tapland(
    "Dismal Backwater", (ManaType.BLUE, ManaType.BLACK), 261
)
