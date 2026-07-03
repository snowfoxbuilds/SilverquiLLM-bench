"""Card implementation for Efflorescence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Efflorescence(Instant):
    """Efflorescence."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Efflorescence")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen_targets = getattr(self, "chosen_targets", [])
        target = chosen_targets[0] if chosen_targets else None
        controller = self.controller
        if not isinstance(target, Creature):
            return
        target_controller = getattr(target, "controller", None)
        if target_controller is None or not game.get_battlefield(target_controller).contains(target):
            return

        add_counter(game, target, "+1/+1", 2)
        if controller is None or getattr(controller, "life_gained_this_turn", 0) <= 0:
            return

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=lambda _game, creature=target: setattr(
                    creature,
                    "keywords",
                    creature.keywords | Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE,
                ),
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
