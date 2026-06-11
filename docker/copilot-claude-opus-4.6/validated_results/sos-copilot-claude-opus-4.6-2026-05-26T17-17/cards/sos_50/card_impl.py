"""Card implementation for Fractal Anomaly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Creature
from engine.types import CardType, Color, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class FractalAnomaly(Instant):
    """Fractal Anomaly — {U} — Instant.

    Create a 0/0 green and blue Fractal creature token and put X +1/+1
    counters on it, where X is the number of cards you've drawn this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Anomaly")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Create a 0/0 Fractal token with X +1/+1 counters."""
        controller = self.controller
        if controller is None:
            return

        # Determine X = cards drawn this turn
        x = getattr(controller, "cards_drawn_this_turn", 0)

        # Create Fractal token
        token = Creature(
            name="Fractal",
            base_power=0,
            base_toughness=0,
            owner=controller,
            controller=controller,
            subtypes={"Fractal"},
        )
        token.is_token = True
        token.colors = {Color.GREEN, Color.BLUE}

        # Put X +1/+1 counters on it
        token.plus_one_counters = x
        token._base_plus_one_counters = x

        # Place on battlefield
        battlefield = game.get_battlefield(controller)
        battlefield.add(token)
