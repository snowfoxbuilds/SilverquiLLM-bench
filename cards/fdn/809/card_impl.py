"""Card implementation for RelicOfProgenitus."""

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



class RelicOfProgenitus(Artifact):
    """Relic of Progenitus — {1} — {T}: Target player exiles a card from their graveyard.
    {1}, Exile Relic of Progenitus: Exile all graveyards. Draw a card."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Relic of Progenitus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{T}: Target player exiles a card from their graveyard.\n"
            "{1}, Exile Relic of Progenitus: Exile all cards from all graveyards. "
            "Draw a card.",
        )
        super().__init__(**kwargs)


__all__ = ["RelicOfProgenitus"]
