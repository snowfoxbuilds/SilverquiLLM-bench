"""Card implementation for FractalAnomaly."""

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



class FractalAnomaly(Instant):
    """Fractal Anomaly — {U} — Create a 0/0 green and blue Fractal creature
    token and put X +1/+1 counters on it, where X is the number of cards
    you've drawn this turn.

    Simplified: creates a 0/0 Fractal token. Counter tracking requires
    draw-count tracking which is not fully wired; defaults to 0 counters
    if no draw count is available.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Anomaly")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 0/0 green and blue Fractal creature token and put X "
            "+1/+1 counters on it, where X is the number of cards you've "
            "drawn this turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Count cards drawn this turn (if tracked)
        drawn_count = getattr(controller, "cards_drawn_this_turn", 0)

        token = Creature(
            name="Fractal",
            base_power=0,
            base_toughness=0,
            subtypes={"Fractal"},
        )
        token.plus_one_counters = drawn_count
        create_token(game, controller, token)


__all__ = ["FractalAnomaly"]
