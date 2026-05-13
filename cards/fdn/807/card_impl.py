"""Card implementation for AltarOfTheBrood."""

from __future__ import annotations


from engine.card import Artifact, ActivatedAbility, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType
from typing import TYPE_CHECKING, Any



class AltarOfTheBrood(Artifact):
    """Altar of the Brood — {1} — Whenever another permanent enters the battlefield
    under your control, each opponent mills a card."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Altar of the Brood")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever another permanent enters the battlefield under your control, "
            "each opponent mills a card.",
        )
        super().__init__(**kwargs)


__all__ = ["AltarOfTheBrood"]
