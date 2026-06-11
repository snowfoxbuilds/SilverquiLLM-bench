"""Card implementation for Eager Glyphmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EagerGlyphmage(Creature):
    """Eager Glyphmage — {3}{W} — 3/3 — Cat Cleric.

    When this creature enters, create a 1/1 white and black Inkling
    creature token with flying.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Eager Glyphmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: create a 1/1 W/B Inkling creature token with flying."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            base_power=1,
            base_toughness=1,
            keywords=Keyword.FLYING,
        )
        create_token(game, controller, token)
