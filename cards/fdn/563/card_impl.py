"""Card implementation for PiratesCutlass."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class PiratesCutlass(Artifact):
    """Pirate's Cutlass — {3} — Equipment. ETB attach to Pirate.
    Equipped creature gets +2/+1. Equip {2}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pirate's Cutlass")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "When this Equipment enters, attach it to target Pirate you control.\n"
            "Equipped creature gets +2/+1.\nEquip {2}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None


__all__ = ["PiratesCutlass"]
