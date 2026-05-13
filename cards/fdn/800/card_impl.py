"""Card implementation for SolRing."""

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



class SolRing(Artifact):
    """Sol Ring — {1} — {T}: Add {C}{C}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sol Ring")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("rules_text", "{T}: Add {C}{C}.")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 2)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect, description="{T}: Add {C}{C}."),
        ]


__all__ = ["SolRing"]
