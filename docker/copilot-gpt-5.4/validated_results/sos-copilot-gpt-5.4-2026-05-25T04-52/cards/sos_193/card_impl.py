"""Card implementation for Growth Curve."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GrowthCurve(Sorcery):
    """Growth Curve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Growth Curve")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj, current_controller=controller: (
                    isinstance(obj, Creature)
                    and current_controller is not None
                    and getattr(obj, "controller", None) is current_controller
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        controller = self.controller
        if not isinstance(target, Creature):
            return
        if not target.is_on_battlefield(game):
            if controller is None or not game.is_fresh_setup_sandbox(controller):
                return
        if controller is not None and getattr(target, "controller", None) is not controller:
            return
        add_counter(game, target, "+1/+1")
        add_counter(game, target, "+1/+1", target.plus_one_counters)
