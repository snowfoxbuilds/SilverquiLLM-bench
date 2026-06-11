"""Card implementation for Heated Argument."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class HeatedArgument(Instant):
    """Heated Argument — {4}{R} — Instant.

    Deals 6 damage to target creature. You may exile a card from your
    graveyard. If you do, also deals 2 damage to that creature's controller.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heated Argument")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)
        self.exile_choice: Any = None

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: 6 damage to target creature, optionally 2 to controller."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target = chosen[0]

        # Deal 6 damage to the target creature
        if hasattr(target, "damage_taken"):
            target.damage_taken += 6
        else:
            target.damage_taken = 6

        # Check if we're exiling a card from graveyard
        exile_card = getattr(self, "exile_choice", None)
        if exile_card is not None:
            controller = self.controller or self.owner
            graveyard = game.get_graveyard(controller)
            if graveyard.contains(exile_card):
                graveyard.remove(exile_card)
                game.get_exile(controller).add(exile_card)

                # Deal 2 damage to creature's controller
                target_controller = getattr(target, "controller", None)
                if target_controller is not None:
                    target_controller.life -= 2

