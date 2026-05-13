"""Card implementation for GildedLotus."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class GildedLotus(Artifact):
    """Gilded Lotus — {5} — {T}: Add three mana of any one color."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gilded Lotus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault("rules_text", "{T}: Add three mana of any one color.")
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
                # Simplified: add 3 colorless (color choice not modelled)
                controller.mana_pool.add(ManaType.COLORLESS, 3)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add three mana of any one color."),
        ]


__all__ = ["GildedLotus"]
