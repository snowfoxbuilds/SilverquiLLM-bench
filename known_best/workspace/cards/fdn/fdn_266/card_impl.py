"""Card implementation for Scoured Barrens."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland

ScouredBarrens = make_gainlife_tapland(
    "Scoured Barrens", (ManaType.WHITE, ManaType.BLACK), 266
)
