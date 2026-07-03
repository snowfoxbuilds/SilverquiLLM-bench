"""Card implementation for Stress Dream."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StressDream(Instant):
    """Stress Dream — {3}{U}{R} — Instant.

    Stress Dream deals 5 damage to up to one target creature. Look at the
    top two cards of your library. Put one of those cards into your hand
    and the other on the bottom of your library.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stress Dream")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState", target: Any = None) -> None:
        from engine.game import deal_damage
        from engine.state_based_actions import resolve_state_based_actions

        controller = self.controller

        # Deal 5 damage to up to one target creature
        if target is not None:
            deal_damage(game, self, target, 5)
            resolve_state_based_actions(game)

        # Look at top two cards, put one in hand, other on bottom
        library = game.get_library(controller)
        top_cards = library.top(2)

        if not top_cards:
            return

        # Remove them from library
        for card in top_cards:
            library.remove(card)

        # Put one into hand (the top card) and the other on bottom
        hand = game.get_hand(controller)
        hand.add(top_cards[-1])  # top card goes to hand

        if len(top_cards) > 1:
            library.add(top_cards[0], position="bottom")
