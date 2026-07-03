"""Card implementation for Wander Off."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import exile
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class WanderOff(Instant):
    """Wander Off."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wander Off")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("rules_text", "Exile target creature.")
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
        target = self.chosen_targets[0] if getattr(self, "chosen_targets", []) else None
        if not isinstance(target, Creature):
            return
        controller = getattr(target, "controller", None)
        if controller is None or not game.get_battlefield(controller).contains(target):
            return
        exile(game, target)
