"""Card implementation for Garrison Excavator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GarrisonExcavator(Creature):
    """Garrison Excavator — {3}{R} — 3/4 Creature — Orc Sorcerer.

    Menace.
    Whenever one or more cards leave your graveyard, create a 2/2 red
    and white Spirit creature token.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Garrison Excavator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.MENACE)
        super().__init__(**kwargs)

    def on_graveyard_leave(self, game: "GameState", event: Any) -> None:
        """Whenever one or more cards leave your graveyard, create a Spirit."""
        # Only trigger for our controller's graveyard
        if event.player is not self.controller:
            return
        # Create a 2/2 red and white Spirit creature token
        token = Creature(
            name="Spirit",
            owner=self.controller,
            controller=self.controller,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(self.controller).add(token)

