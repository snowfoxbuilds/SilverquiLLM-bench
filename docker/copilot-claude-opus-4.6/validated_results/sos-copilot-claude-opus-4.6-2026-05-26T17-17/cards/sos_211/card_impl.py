"""Card implementation for Prismari Charm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class PrismariCharm(Instant):
    """Prismari Charm — {U}{R} — Instant.

    Choose one —
    • Surveil 2, then draw a card.
    • Prismari Charm deals 1 damage to each of one or two targets.
    • Return target nonland permanent to its owner's hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Prismari Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}{R}"))
        super().__init__(**kwargs)
        self.chosen_mode: int = 0
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return targeting requirements for each mode."""
        # Return a list of target requirements per mode
        return [
            {"description": "Surveil 2, then draw"},
            {"description": "1 damage to one or two targets"},
            {"description": "nonland permanent", "filter": "nonland"},
        ]

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner
        if self.chosen_mode == 0:
            # Surveil 2, then draw a card
            library = game.get_library(controller)
            graveyard = game.get_graveyard(controller)
            cards_to_surveil = library.top(2)
            for card in cards_to_surveil:
                library.remove(card)
                graveyard.add(card)
            # Draw a card
            from engine.game import draw_card
            draw_card(game, controller)
        elif self.chosen_mode == 1:
            # Deal 1 damage to each of one or two targets
            for target in self.chosen_targets:
                target.damage_taken = getattr(target, "damage_taken", 0) + 1
        elif self.chosen_mode == 2:
            # Return target nonland permanent to its owner's hand
            for target in self.chosen_targets:
                owner = target.owner
                bf = game.get_battlefield(owner)
                hand = game.get_hand(owner)
                if target in bf:
                    bf.remove(target)
                    hand.add(target)
