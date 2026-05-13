"""Card implementation for WisdomOfAges."""

from __future__ import annotations


from engine.card import Artifact, Creature, Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any
import math

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class WisdomOfAges(Sorcery):
    """Wisdom of Ages — {4}{U}{U}{U} — Return all instant and sorcery cards
    from your graveyard to your hand. Exile Wisdom of Ages.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wisdom of Ages")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Return all instant and sorcery cards from your graveyard to "
            "your hand. You have no maximum hand size for the rest of the "
            "game.\nExile Wisdom of Ages.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        hand = game.get_hand(controller)

        # Find all instant/sorcery cards in graveyard
        to_return = []
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                to_return.append(card)

        for card in to_return:
            graveyard.remove(card)
            hand.add(card)

        # Controller has no maximum hand size for the rest of the game
        controller.no_maximum_hand_size = True

        # Exile Wisdom of Ages instead of going to graveyard
        self._exile_on_resolve = True


__all__ = ["WisdomOfAges"]
