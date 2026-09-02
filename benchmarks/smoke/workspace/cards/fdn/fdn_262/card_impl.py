"""Card implementation for Evolving Wilds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land
from engine.card_queries import choose_object
from engine.types import CardType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EvolvingWilds(Land):
    """Evolving Wilds — Land.

    {T}, Sacrifice this land: Search your library for a basic land card,
    put it onto the battlefield tapped, then shuffle.

    FDN collector number 262.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Evolving Wilds")
        kwargs.setdefault(
            "rules_text",
            "{T}, Sacrifice this land: Search your library for a basic "
            "land card, put it onto the battlefield tapped, then shuffle.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            src.is_tapped = True
            from engine.game import sacrifice

            sacrifice(game, controller, src)
            return True

        def _effect(game: "GameState") -> None:
            controller = source.controller or source.owner
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            basics = [
                c
                for c in library.get_all()
                if Supertype.BASIC in getattr(c, "supertypes", set())
                and CardType.LAND in getattr(c, "card_types", set())
            ]
            if not basics:
                library.shuffle()
                return
            if len(basics) == 1:
                chosen = basics[0]
            else:
                chosen = choose_object(
                    game,
                    controller,
                    basics,
                    "Choose a basic land card to put onto the battlefield tapped",
                    source_card=source,
                )
            chosen.controller = controller
            chosen.is_tapped = True
            from engine.zones import move_to_zone

            move_to_zone(game, chosen, Zone.LIBRARY, Zone.BATTLEFIELD)
            library.shuffle()

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{T}, Sacrifice this land: Search your library "
                "for a basic land card, put it onto the battlefield tapped, "
                "then shuffle.",
            )
        ]
