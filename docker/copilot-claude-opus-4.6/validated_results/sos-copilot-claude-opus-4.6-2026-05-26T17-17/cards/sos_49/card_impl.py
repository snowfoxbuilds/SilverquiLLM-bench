"""Card implementation for Flow State."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery, Instant as InstantCard
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class FlowState(Sorcery):
    """Flow State — {1}{U} — Sorcery.

    Look at the top three cards of your library. Put one into your hand and
    the rest on the bottom. If there is an instant AND a sorcery in your
    graveyard, instead put two into your hand and the rest on the bottom.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Flow State")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Look at top 3, draw 1 or 2 based on graveyard condition."""
        controller = self.controller
        if controller is None:
            return

        # Check graveyard for instant AND sorcery
        graveyard = game.get_graveyard(controller)
        gy_cards = graveyard.get_all()
        has_instant = any(CardType.INSTANT in getattr(c, "card_types", set()) for c in gy_cards)
        has_sorcery = any(CardType.SORCERY in getattr(c, "card_types", set()) for c in gy_cards)
        enhanced = has_instant and has_sorcery

        draw_count = 2 if enhanced else 1

        # Look at top 3 cards
        library = game.get_library(controller)
        hand = game.get_hand(controller)
        lib_cards = library.get_all()

        top_3 = lib_cards[-3:] if len(lib_cards) >= 3 else lib_cards[:]

        # Put draw_count to hand (from top)
        to_hand = top_3[-draw_count:] if len(top_3) >= draw_count else top_3[:]
        to_bottom = [c for c in top_3 if c not in to_hand]

        for card in to_hand:
            library.remove(card)
            hand.add(card)

        for card in to_bottom:
            library.remove(card)
            library.add(card, position="bottom")
