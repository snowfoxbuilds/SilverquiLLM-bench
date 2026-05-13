"""Card implementation for MaskOfMemory."""

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



class MaskOfMemory(Artifact):
    """Mask of Memory — {2} — Whenever equipped creature deals combat damage,
    draw two cards then discard a card. Equip {1}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mask of Memory")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Whenever equipped creature deals combat damage to a player, "
            "you may draw two cards. If you do, discard a card.\nEquip {1}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None


__all__ = ["MaskOfMemory"]
