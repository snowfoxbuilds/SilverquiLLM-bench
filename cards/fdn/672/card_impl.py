"""Card implementation for DiamondMare."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class DiamondMare(ArtifactCreature):
    """Diamond Mare — {2} — 1/3 Horse. Choose a color; gain 1 life when you
    cast a spell of that color."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Diamond Mare")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Horse"}
        kwargs.setdefault(
            "rules_text",
            "As this creature enters, choose a color.\n"
            "Whenever you cast a spell of the chosen color, you gain 1 life.",
        )
        super().__init__(**kwargs)
        self.chosen_color: str | None = None


__all__ = ["DiamondMare"]
