"""Card implementation for Fractal Anomaly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import Color, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class FractalAnomaly(Instant):
    """Fractal Anomaly."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Anomaly")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        draw_count = getattr(controller, "cards_drawn_this_turn", 0)
        token = Creature(
            name="Fractal",
            base_power=0,
            base_toughness=0,
            subtypes={"Fractal"},
            owner=controller,
            controller=controller,
        )
        token.colors = {Color.GREEN, Color.BLUE}  # type: ignore[attr-defined]
        token.plus_one_counters = draw_count
        token._base_plus_one_counters = draw_count
        create_token(game, controller, token)
