"""Card implementation for Jadzi, Steward of Fate // Oracle's Gift."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class JadziStewardOfFateOraclesGift(Creature):
    """Jadzi, Steward of Fate // Oracle's Gift — {2}{U} Legendary Creature — Human Wizard 2/4.

    Jadzi enters prepared.
    When Jadzi enters, draw two cards, then discard two cards.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Jadzi, Steward of Fate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_enter_battlefield(self, game: "GameState") -> None:
        from engine.game import draw_card, discard

        # Enters prepared
        self.is_prepared = True

        controller = self.controller

        # Draw two cards
        draw_card(game, controller)
        draw_card(game, controller)

        # Discard two cards
        hand = game.get_hand(controller)
        cards_to_discard = list(hand)[:2]
        for card in cards_to_discard:
            discard(game, controller, card)
