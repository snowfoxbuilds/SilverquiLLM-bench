"""Card implementation for Zimone's Experiment."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ZimonesExperiment(Sorcery):
    """Zimone's Experiment — {3}{G} — Sorcery.

    Look at the top five cards of your library. You may reveal up to two
    creature and/or land cards from among them, then put the rest on the
    bottom of your library in a random order. Put all land cards revealed
    this way onto the battlefield tapped and put all creature cards revealed
    this way into your hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zimone's Experiment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Look at top 5, reveal up to 2 creature/land, route accordingly."""
        controller = self.controller or self.owner
        if controller is None:
            return

        library = game.get_library(controller)
        hand = game.get_hand(controller)
        battlefield = game.get_battlefield(controller)

        # Look at the top 5 cards
        top_cards = library.top(min(5, len(library.cards)))
        # Remove them from library
        for card in top_cards:
            library.remove(card)

        # Player chooses up to 2 creature/land cards to reveal
        reveal_choices = getattr(controller, "reveal_choices", [])

        revealed = []
        rest = []
        for card in top_cards:
            if card in reveal_choices and len(revealed) < 2:
                revealed.append(card)
            else:
                rest.append(card)

        # Put rest on bottom in random order
        random.shuffle(rest)
        for card in rest:
            library.add(card, position="bottom")

        # Route revealed cards
        for card in revealed:
            card_types = getattr(card, "card_types", set())
            if CardType.LAND in card_types:
                card.tapped = True
                battlefield.add(card)
            elif CardType.CREATURE in card_types:
                hand.add(card)
