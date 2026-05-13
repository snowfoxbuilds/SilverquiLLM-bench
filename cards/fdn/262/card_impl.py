"""Card implementation for Evolving Wilds."""

from __future__ import annotations

import random

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.game import sacrifice


class EvolvingWilds(Land):
    """Evolving Wilds (#262) — {T}, Sacrifice this land: Search your library
    for a basic land card, put it onto the battlefield tapped, then shuffle."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Evolving Wilds")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        # Evolving Wilds has no mana abilities (its ability isn't a mana ability).
        return []

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            """Tap and sacrifice."""
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            # Sacrifice the land
            controller = src.controller
            if controller is not None:
                battlefield = getattr(controller, "battlefield", None)
                if battlefield is not None and src in battlefield:
                    battlefield.remove(src)
                graveyard = getattr(controller, "graveyard", None)
                if graveyard is not None:
                    graveyard.append(src)
            return True

        def _effect(game: Any) -> None:
            """Search library for a basic land, put it onto the battlefield tapped, shuffle."""
            controller = source.controller
            if controller is None:
                return
            library = getattr(controller, "library", None)
            if library is None:
                return
            # Find a basic land in the library
            basic_land = None
            for card in library:
                if getattr(card, "is_basic_land", False):
                    basic_land = card
                    break
            if basic_land is not None:
                library.remove(basic_land)
                basic_land.is_tapped = True
                basic_land.controller = controller
                battlefield = getattr(controller, "battlefield", None)
                if battlefield is not None:
                    battlefield.append(basic_land)
                # Shuffle library
                import random
                random.shuffle(library)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.",
        )]
