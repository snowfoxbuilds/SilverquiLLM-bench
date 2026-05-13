"""Card implementation for FeldonsCane."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class FeldonsCane(Artifact):
    """Feldon's Cane — {1} — {T}, Exile: Shuffle your graveyard into your library."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Feldon's Cane")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{T}, Exile this artifact: Shuffle your graveyard into your library.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import exile
            from engine.types import Zone
            controller = source.controller
            if controller is not None:
                graveyard = controller.zones[Zone.GRAVEYARD]
                library = controller.zones[Zone.LIBRARY]
                if graveyard is not None and library is not None:
                    for card in list(graveyard.get_all()):
                        graveyard.remove(card)
                        library.add(card)
                    library.shuffle()
                exile(game, source)

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{T}, Exile: Shuffle graveyard into library.",
            ),
        ]


__all__ = ["FeldonsCane"]
