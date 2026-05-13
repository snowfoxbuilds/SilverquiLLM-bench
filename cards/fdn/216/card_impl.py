"""Card implementation for PursueThePast."""

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



class PursueThePast(Sorcery):
    """Pursue the Past — {R}{W} — You gain 2 life. You may discard a card.
    If you do, draw two cards.

    Flashback is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pursue the Past")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault(
            "rules_text",
            "You gain 2 life. You may discard a card. If you do, draw two "
            "cards.\nFlashback {2}{R}{W}",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import draw_card, discard

        controller = self.controller
        if controller is None:
            return

        # Gain 2 life
        controller.life += 2

        # May discard a card; if so, draw two
        hand = game.get_hand(controller)
        cards_in_hand = list(hand.get_all())
        if cards_in_hand:
            discard(game, controller, cards_in_hand[0])
            draw_card(game, controller)
            draw_card(game, controller)


__all__ = ["PursueThePast"]
