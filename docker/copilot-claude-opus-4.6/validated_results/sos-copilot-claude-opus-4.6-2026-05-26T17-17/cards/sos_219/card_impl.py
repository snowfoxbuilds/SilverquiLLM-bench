"""Card implementation for Rapturous Moment."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RapturousMoment(Sorcery):
    """Rapturous Moment — {4}{U}{R} — Sorcery.

    Draw three cards, then discard two cards. Add {U}{U}{R}{R}{R}.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rapturous Moment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Draw three cards, then discard two cards. Add {U}{U}{R}{R}{R}.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Draw 3, discard 2, add {U}{U}{R}{R}{R}."""
        from engine.game import draw_card, discard

        player = self.controller

        # Draw three cards
        draw_card(game, player)
        draw_card(game, player)
        draw_card(game, player)

        # Discard two cards (first two in hand)
        hand = game.get_hand(player)
        hand_cards = hand.get_all()
        cards_to_discard = list(hand_cards[:2])
        for card in cards_to_discard:
            discard(game, player, card)

        # Add mana: {U}{U}{R}{R}{R}
        player.mana_pool.add(ManaType.BLUE, 2)
        player.mana_pool.add(ManaType.RED, 3)
