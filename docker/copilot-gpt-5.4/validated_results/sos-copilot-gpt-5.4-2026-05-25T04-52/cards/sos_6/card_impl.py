"""Card implementation for Ajani's Response."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AjanisResponse(Instant):
    """Ajani's Response."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ajani's Response")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        kwargs.setdefault(
            "rules_text",
            "This spell costs {3} less to cast if it targets a tapped creature.\n"
            "Destroy target creature.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def cost_reduction(self, game: GameState) -> int:
        targets = getattr(self, "_casting_targets", getattr(self, "chosen_targets", []))
        target = targets[0] if targets else None
        return 3 if getattr(target, "is_tapped", False) else 0

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if target is None:
            return
        destroy(game, target)
