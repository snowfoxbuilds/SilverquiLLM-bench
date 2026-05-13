"""Card implementation for CultivatorsCaravan."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class CultivatorsCaravan(Artifact):
    """Cultivator's Caravan — {3} — Vehicle 5/5. {T}: Add any color. Crew 3."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cultivator's Caravan")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vehicle"}
        kwargs.setdefault(
            "rules_text",
            "{T}: Add one mana of any color.\nCrew 3",
        )
        super().__init__(**kwargs)
        self.base_power: int = 5
        self.base_toughness: int = 5
        self.crew_cost: int = 3

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
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add one mana of any color."),
        ]


__all__ = ["CultivatorsCaravan"]
