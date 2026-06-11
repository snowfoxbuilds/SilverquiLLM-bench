"""Card implementation for Embrace the Paradox."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmbraceTheParadox(Instant):
    """Embrace the Paradox — {3}{G}{U} — Instant.

    Draw three cards. You may put a land card from your hand onto the
    battlefield tapped.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Embrace the Paradox")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Draw three cards, then optionally put a land from hand onto battlefield tapped."""
        from engine.game import draw_card

        controller = self.controller
        if controller is None:
            return

        # Draw three cards
        for _ in range(3):
            draw_card(game, controller)

        # May put a land card from hand onto battlefield tapped
        hand = game.get_hand(controller)
        hand_cards = hand.get_all()
        land_cards = [c for c in hand_cards if CardType.LAND in getattr(c, "card_types", set())]

        if land_cards:
            land = land_cards[0]
            hand.remove(land)
            land.tapped = True
            bf = game.get_battlefield(controller)
            bf.add(land)
