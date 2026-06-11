"""Card implementation for Snarl Song."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import Color, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_fractal_token(counter_count: int) -> Creature:
    token = Creature(
        name="Fractal",
        base_power=0,
        base_toughness=0,
        subtypes={"Fractal"},
    )
    token.colors = {Color.GREEN, Color.BLUE}  # type: ignore[attr-defined]
    token.plus_one_counters = counter_count
    token._base_plus_one_counters = counter_count
    token.snapshot_current_characteristics()
    return token


class SnarlSong(Sorcery):
    """Snarl Song."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Snarl Song")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        color_count = len(
            {color for color in getattr(self, "colors_spent", []) if isinstance(color, Color)}
        )
        create_token(game, controller, _create_fractal_token(color_count))
        create_token(game, controller, _create_fractal_token(color_count))

        if color_count <= 0:
            return

        controller.life += color_count
        controller.life_gained_this_turn = getattr(controller, "life_gained_this_turn", 0) + color_count
        game.trigger_manager.fire_event(
            game,
            GainsLifeTriggeredEvent(player=controller, amount=color_count),
        )
