"""Card implementation for SorcerousSpyglass."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class SorcerousSpyglass(Artifact):
    """Sorcerous Spyglass — {2} — As enters, look at opponent's hand, choose a name.
    Activated abilities of sources with chosen name can't be activated."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sorcerous Spyglass")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault(
            "rules_text",
            "As this artifact enters, look at an opponent's hand, then choose any "
            "card name.\nActivated abilities of sources with the chosen name can't "
            "be activated unless they're mana abilities.",
        )
        super().__init__(**kwargs)
        self.chosen_name: str | None = None


__all__ = ["SorcerousSpyglass"]
