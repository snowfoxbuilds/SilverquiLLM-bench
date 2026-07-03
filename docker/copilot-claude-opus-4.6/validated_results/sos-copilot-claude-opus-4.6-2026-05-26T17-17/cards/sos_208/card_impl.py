"""Card implementation for Paradox Surveyor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ParadoxSurveyor(Creature):
    """Paradox Surveyor — {G}{G/U}{U} — 3/3 — Creature — Elf Druid.

    Reach
    When this creature enters, look at the top five cards of your library.
    You may reveal a land card or a card with {X} in its mana cost from among
    them and put it into your hand. Put the rest on the bottom of your library
    in a random order.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Paradox Surveyor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{G/U}{U}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def on_enter_battlefield(self, game: "GameState", choice: Any = None, **kwargs: Any) -> None:
        """ETB: look at top 5, may take a land or {X} card to hand."""
        controller = self.controller
        library = game.get_library(controller)
        all_cards = library.get_all()

        # Top 5 cards (top = end of list)
        top_five = all_cards[-5:] if len(all_cards) >= 5 else list(all_cards)

        if choice is not None:
            # Validate choice is in the top 5
            if choice not in top_five:
                raise ValueError("Chosen card is not in the top five cards of the library.")
            # Validate choice is a land or has {X} in mana cost
            is_land = hasattr(choice, 'card_types') and CardType.LAND in choice.card_types
            has_x = hasattr(choice, 'mana_cost') and getattr(choice.mana_cost, 'x_count', 0) > 0
            if not is_land and not has_x:
                raise ValueError("Choice must be a land card or a card with {X} in its mana cost.")
            # Move choice to hand
            library.remove(choice)
            game.get_hand(controller).add(choice)

        # Remaining top cards go to bottom (in random order - we just move them)
        remaining = [c for c in top_five if c is not choice]
        for c in remaining:
            library.remove(c)
        import random
        random.shuffle(remaining)
        for c in remaining:
            library.add(c, position="bottom")
