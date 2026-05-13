"""Card implementation for ExpeditionMap."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class ExpeditionMap(Artifact):
    """Expedition Map — {1} — {2}, {T}, Sacrifice: Search for a land card."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Expedition Map")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{2}, {T}, Sacrifice this artifact: Search your library for a land card, "
            "reveal it, put it into your hand, then shuffle.",
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
            from engine.game import sacrifice
            from engine.types import Zone
            controller = source.controller
            if controller is not None:
                # Sacrifice Expedition Map
                sacrifice(game, controller, source)
                # Search library for a land card, put it in hand, shuffle
                library = controller.zones[Zone.LIBRARY]
                hand = controller.zones[Zone.HAND]
                land_card = None
                for card in library.get_all():
                    if CardType.LAND in getattr(card, "card_types", set()):
                        land_card = card
                        break
                if land_card is not None:
                    library.remove(land_card)
                    hand.add(land_card)
                library.shuffle()

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{2}, {T}, Sacrifice: Search for a land card.",
            ),
        ]


__all__ = ["ExpeditionMap"]
