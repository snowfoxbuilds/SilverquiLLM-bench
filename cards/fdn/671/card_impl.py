"""Card implementation for DarksteelColossus."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class DarksteelColossus(ArtifactCreature):
    """Darksteel Colossus — {11} — 11/11. Trample, Indestructible.
    If would go to graveyard, shuffle into library instead."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Darksteel Colossus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{11}"))
        kwargs.setdefault("base_power", 11)
        kwargs.setdefault("base_toughness", 11)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Golem"}
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE)
        kwargs.setdefault(
            "rules_text",
            "Trample, indestructible\n"
            "If Darksteel Colossus would be put into a graveyard from anywhere, "
            "reveal Darksteel Colossus and shuffle it into its owner's library instead.",
        )
        super().__init__(**kwargs)


__all__ = ["DarksteelColossus"]
