"""Card implementation for SeizeTheSpoils."""

from __future__ import annotations


from engine.card import Artifact, Creature, Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any
import math

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class SeizeTheSpoils(Sorcery):
    """Seize the Spoils — {2}{R} — As an additional cost, discard a card.
    Draw two cards and create a Treasure token.

    The additional cost (discard) is not enforced at cast time; it is
    applied on resolution.  Treasure token is a simple Artifact token.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Seize the Spoils")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "As an additional cost to cast this spell, discard a card.\n"
            "Draw two cards and create a Treasure token.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token, discard, draw_card

        controller = self.controller
        if controller is None:
            return

        # Additional cost: discard a card (simplified — done on resolution)
        hand = game.get_hand(controller)
        hand_cards = hand.get_all()
        if hand_cards:
            discard(game, controller, hand_cards[0])

        # Draw 2 cards
        draw_card(game, controller)
        draw_card(game, controller)

        # Create a Treasure token
        treasure = Artifact(
            name="Treasure",
            rules_text=(
                "{T}, Sacrifice this token: Add one mana of any color."
            ),
        )
        treasure.is_token = True
        create_token(game, controller, treasure)


__all__ = ["SeizeTheSpoils"]
