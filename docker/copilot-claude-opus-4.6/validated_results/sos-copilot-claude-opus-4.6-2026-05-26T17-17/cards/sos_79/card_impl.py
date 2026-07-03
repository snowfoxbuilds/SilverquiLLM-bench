"""Card implementation for Dissection Practice."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class DissectionPractice(Instant):
    """Dissection Practice — {B} — Instant.

    Target opponent loses 1 life and you gain 1 life.
    Up to one target creature gets +1/+1 until end of turn.
    Up to one target creature gets -1/-1 until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dissection Practice")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return
        # First target: opponent who loses 1 life
        opponent = targets[0]
        if opponent is not None:
            opponent.life -= 1
            controller = self.controller or self.owner
            controller.life += 1
        # Second target (optional): creature gets +1/+1 until end of turn
        if len(targets) > 1 and targets[1] is not None:
            creature = targets[1]
            creature.modified_power += 1
            creature.modified_toughness += 1
        # Third target (optional): creature gets -1/-1 until end of turn
        if len(targets) > 2 and targets[2] is not None:
            creature = targets[2]
            creature.modified_power -= 1
            creature.modified_toughness -= 1
