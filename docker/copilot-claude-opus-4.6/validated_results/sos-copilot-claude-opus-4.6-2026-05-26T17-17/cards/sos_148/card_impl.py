"""Card implementation for Follow the Lumarets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class FollowTheLumarets(Sorcery):
    """Follow the Lumarets — {1}{G} — Sorcery.

    Infusion — Look at the top four cards of your library. You may reveal a
    creature or land card from among them and put it into your hand. If you
    gained life this turn, you may instead reveal two creature and/or land
    cards from among them and put them into your hand. Put the rest on the
    bottom of your library in a random order.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Follow the Lumarets")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Look at top 4, pick creature/land (or 2 if life gained)."""
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        # Take top 4 cards
        top_cards = library.top(min(4, len(library)))
        # Remove them from library (top() returns bottom-to-top order, last is top)
        for card in top_cards:
            library.remove(card)

        # Find creature or land cards
        def is_creature_or_land(c: Any) -> bool:
            ct = getattr(c, "card_types", set())
            return CardType.CREATURE in ct or CardType.LAND in ct

        eligible = [c for c in top_cards if is_creature_or_land(c)]

        # Check if player gained life this turn (infusion)
        life_gained = getattr(controller, "life_gained_this_turn", 0)
        max_picks = 2 if life_gained > 0 else 1

        # Pick up to max_picks from eligible
        chosen = eligible[:max_picks]

        # Put chosen into hand
        hand = game.get_hand(controller)
        for card in chosen:
            hand.add(card)
            top_cards.remove(card)

        # Put the rest on the bottom in random order
        import random
        random.shuffle(top_cards)
        for card in top_cards:
            library.add(card, position="bottom")
