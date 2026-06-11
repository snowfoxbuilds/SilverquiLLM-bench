"""Card implementation for Environmental Scientist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class EnvironmentalScientist(Creature):
    """Environmental Scientist — {1}{G} — Creature — Human Druid — 2/2.

    When this creature enters, you may search your library for a basic land
    card, reveal it, put it into your hand, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Environmental Scientist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Human", "Druid"})
        super().__init__(**kwargs)

    def on_enter_battlefield(self, game: "GameState") -> None:
        """ETB: search library for a basic land, put it into hand, shuffle."""
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        # Basic land names for recognition
        _BASIC_LAND_NAMES = {"Forest", "Island", "Plains", "Mountain", "Swamp"}

        # Find a basic land in the library
        basic_land = None
        for card in library:
            card_types = getattr(card, "card_types", set())
            if CardType.LAND not in card_types:
                continue
            supertypes = getattr(card, "supertypes", set())
            # Check by supertype or by name
            if Supertype.BASIC in supertypes or card.name in _BASIC_LAND_NAMES:
                basic_land = card
                break

        if basic_land is None:
            return

        # Move from library to hand
        library.remove(basic_land)
        game.get_hand(controller).add(basic_land)
        # Shuffle library
        library.shuffle()
        library.was_shuffled = True
