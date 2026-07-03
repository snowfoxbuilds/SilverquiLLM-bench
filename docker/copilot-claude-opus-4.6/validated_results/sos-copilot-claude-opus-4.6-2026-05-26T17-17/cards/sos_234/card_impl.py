"""Card implementation for Stirring Honormancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StirringHonormancer(Creature):
    """Stirring Honormancer — {2}{W}{W/B}{B} — Creature — Rhino Bard — 4/5.

    When this creature enters, look at the top X cards of your library,
    where X is the number of creatures you control. Put one of those cards
    into your hand and the rest into your graveyard.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stirring Honormancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{W/B}{B}"))
        kwargs.setdefault("subtypes", {"Rhino", "Bard"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def on_enter(self, game: "GameState") -> None:
        """ETB: look at top X cards, put 1 to hand, rest to graveyard."""
        controller = self.controller
        # Count creatures controlled
        bf = game.get_battlefield(controller)
        x = sum(1 for perm in bf.get_all() if CardType.CREATURE in getattr(perm, "card_types", set()))

        if x == 0:
            return

        library = game.get_library(controller)
        top_cards = library.top(x)

        if not top_cards:
            return

        # Remove them from library
        for card in top_cards:
            library.remove(card)

        # Put one into hand (top card) and rest into graveyard
        hand = game.get_hand(controller)
        hand.add(top_cards[-1])  # top card goes to hand

        graveyard = game.get_graveyard(controller)
        for card in top_cards[:-1]:
            graveyard.add(card)
