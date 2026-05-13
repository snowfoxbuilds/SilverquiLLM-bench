"""Card implementation for RapturousMoment."""

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



class RapturousMoment(Sorcery):
    """Rapturous Moment — {4}{U}{R} — Draw 3, discard 2, add {U}{U}{R}{R}{R}.

    The mana-adding part is not implemented; only draw 3 + discard 2.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rapturous Moment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Draw three cards, then discard two cards. Add {U}{U}{R}{R}{R}.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import draw_card, discard

        controller = self.controller
        if controller is None:
            return

        # Draw 3
        for _ in range(3):
            draw_card(game, controller)

        # Discard 2 (first 2 cards from hand if available)
        hand = game.get_hand(controller)
        cards_in_hand = list(hand.get_all())
        to_discard = cards_in_hand[:2]
        for card in to_discard:
            discard(game, controller, card)


__all__ = ["RapturousMoment"]
