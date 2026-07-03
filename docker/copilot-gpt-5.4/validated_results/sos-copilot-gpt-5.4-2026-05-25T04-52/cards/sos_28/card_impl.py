"""Card implementation for Rapier Wit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import add_counter, draw_card, tap
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RapierWit(Instant):
    """Rapier Wit."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rapier Wit")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
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
        if isinstance(target, Creature):
            tap(game, target)
            if self.controller is game.active_player:
                add_counter(game, target, "stun")
        if self.controller is not None:
            draw_card(game, self.controller)
