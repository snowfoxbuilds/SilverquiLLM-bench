"""Card implementation for Planar Engineering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PlanarEngineering(Sorcery):
    """Planar Engineering — {3}{G} — Sorcery.

    Sacrifice two lands. Search your library for four basic land cards,
    put them onto the battlefield tapped, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Planar Engineering")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Sacrifice two lands, fetch four basics tapped."""
        controller = self.controller
        if controller is None:
            return

        # Find lands on controller's battlefield
        bf = game.get_battlefield(controller)
        lands = [c for c in bf.get_all() if CardType.LAND in getattr(c, "card_types", set())]

        # Need at least two lands to sacrifice
        if len(lands) < 2:
            return

        # Sacrifice two lands (move to graveyard)
        gy = game.get_graveyard(controller)
        for land in lands[:2]:
            bf.remove(land)
            gy.add(land)

        # Search library for up to four basic lands
        library = game.get_library(controller)
        basics = [c for c in library.get_all() if getattr(c, "is_basic", False)]
        to_fetch = basics[:4]

        # Put them onto the battlefield tapped
        for basic in to_fetch:
            library.remove(basic)
            basic.is_tapped = True
            basic.tapped = True
            bf.add(basic)
