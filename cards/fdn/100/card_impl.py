"""Card implementation for SendInThePest."""

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



class SendInThePest(Sorcery):
    """Send in the Pest — {1}{B} — Each opponent discards a card. You create
    a 1/1 black and green Pest creature token with "Whenever this token
    attacks, you gain 1 life."

    The Pest trigger ability is not implemented; just creates a 1/1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Send in the Pest")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Each opponent discards a card. You create a 1/1 black and green "
            'Pest creature token with "Whenever this token attacks, you gain '
            '1 life."',
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token, discard

        controller = self.controller
        if controller is None:
            return

        # Each opponent discards a card
        for player in game.players:
            if player is controller:
                continue
            hand = game.get_hand(player)
            cards = list(hand.get_all())
            if cards:
                discard(game, player, cards[0])

        # Create 1/1 Pest token
        token = Creature(
            name="Pest",
            base_power=1,
            base_toughness=1,
            subtypes={"Pest"},
        )
        create_token(game, controller, token)


__all__ = ["SendInThePest"]
