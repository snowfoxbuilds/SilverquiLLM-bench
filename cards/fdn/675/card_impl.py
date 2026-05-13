"""Card implementation for GateColossus."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class GateColossus(ArtifactCreature):
    """Gate Colossus — {8} — 8/8 Construct. Affinity for Gates.
    Can't be blocked by power ≤ 2."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gate Colossus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{8}"))
        kwargs.setdefault("base_power", 8)
        kwargs.setdefault("base_toughness", 8)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Construct"}
        kwargs.setdefault(
            "rules_text",
            "Affinity for Gates\n"
            "This creature can't be blocked by creatures with power 2 or less.\n"
            "Whenever a Gate you control enters, you may put this card from your "
            "graveyard on top of your library.",
        )
        super().__init__(**kwargs)


__all__ = ["GateColossus"]
