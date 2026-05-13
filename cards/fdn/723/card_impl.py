"""Card implementation for AdaptiveAutomaton."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class AdaptiveAutomaton(ArtifactCreature):
    """Adaptive Automaton — {3} — 2/2 Construct. Choose a creature type.
    Is the chosen type. Other creatures of chosen type get +1/+1."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Adaptive Automaton")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Construct"}
        kwargs.setdefault(
            "rules_text",
            "As this creature enters, choose a creature type.\n"
            "This creature is the chosen type in addition to its other types.\n"
            "Other creatures you control of the chosen type get +1/+1.",
        )
        super().__init__(**kwargs)
        self.chosen_type: str | None = None


__all__ = ["AdaptiveAutomaton"]
