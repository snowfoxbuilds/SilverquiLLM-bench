"""Card implementation for Charging Strifeknight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ChargingStrifeknight(Creature):
    """Charging Strifeknight — {2}{R} — 3/3 Creature — Spirit Knight.

    Haste
    {T}, Discard a card: Draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Charging Strifeknight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("subtypes", {"Spirit", "Knight"})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def can_activate_ability(self, game: "GameState", index: int = 0) -> bool:
        """Can activate if untapped and has a card in hand to discard."""
        if self.is_tapped:
            return False
        controller = self.controller or self.owner
        hand = game.get_hand(controller)
        return len(hand) > 0

    def activate_ability(self, game: "GameState", index: int = 0, discard: Any = None) -> None:
        """Tap, discard a card: Draw a card."""
        from engine.game import draw_card

        controller = self.controller or self.owner

        # Tap
        self.is_tapped = True

        # Discard
        if discard is not None:
            hand = game.get_hand(controller)
            if hand.contains(discard):
                hand.remove(discard)
                graveyard = game.get_graveyard(controller)
                graveyard.add(discard)

        # Draw
        draw_card(game, controller)
