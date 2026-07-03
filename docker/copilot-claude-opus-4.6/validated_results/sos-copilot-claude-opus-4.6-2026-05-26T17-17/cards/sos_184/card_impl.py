"""Card implementation for Dina's Guidance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class DinasGuidance(Instant):
    """Dina's Guidance — {1}{B}{G} — Instant.

    Search your library for a creature card, reveal it, put it into your hand
    or graveyard, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dina's Guidance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Search library for a creature card, put it in hand or graveyard, shuffle."""
        controller = self.controller
        library = controller.zones[Zone.LIBRARY]

        # Find creature cards in library
        creatures = [
            card for card in library.get_all()
            if CardType.CREATURE in getattr(card, "card_types", set())
        ]

        if creatures:
            # Take the first creature found (deterministic choice)
            chosen = creatures[0]
            library.remove(chosen)

            # Put into hand (default choice for deterministic player)
            hand = controller.zones[Zone.HAND]
            hand.add(chosen)

        # Shuffle library
        import random
        lib_cards = list(library.get_all())
        for card in list(library.get_all()):
            library.remove(card)
        random.shuffle(lib_cards)
        for card in lib_cards:
            library.add(card)
