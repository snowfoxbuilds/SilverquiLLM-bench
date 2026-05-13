"""Card implementation for ArcaneSigNet."""

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



class ArcaneSigNet(Artifact):
    """Arcane Signet — {2} — {T}: Add {C} (simplified)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arcane Signet")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("rules_text", "{T}: Add one mana of any color in your commander's color identity.")
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
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect, description="{T}: Add {C}."),
        ]


__all__ = ["ArcaneSigNet"]
