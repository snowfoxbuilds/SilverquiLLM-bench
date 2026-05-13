"""Card implementation for ThreeTreeMascot."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class ThreeTreeMascot(ArtifactCreature):
    """Three Tree Mascot — {2} — 2/1 Shapeshifter. Changeling.
    {1}: Add one mana of any color. Once each turn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Three Tree Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Shapeshifter"}
        kwargs.setdefault(
            "rules_text",
            "Changeling\n"
            "{1}: Add one mana of any color. Activate only once each turn.",
        )
        super().__init__(**kwargs)
        # Changeling means this is every creature type
        self.is_changeling = True

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return True  # {1} cost not tracked

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_cost, mana_produced=_effect,
                        description="{1}: Add one mana of any color."),
        ]


__all__ = ["ThreeTreeMascot"]
