"""Card implementation for ElixirOfImmortality."""

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



class ElixirOfImmortality(Artifact):
    """Elixir of Immortality — {1} — {2}, {T}: You gain 5 life. Shuffle
    Elixir of Immortality and your graveyard into your library."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elixir of Immortality")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{2}, {T}: You gain 5 life. Shuffle Elixir of Immortality "
            "and your graveyard into your library.",
        )
        super().__init__(**kwargs)


__all__ = ["ElixirOfImmortality"]
