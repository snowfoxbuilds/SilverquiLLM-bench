"""Card implementation for Grapple with Death."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Artifact, Creature, Sorcery
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GrappleWithDeath(Sorcery):
    """Grapple with Death."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grapple with Death")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Artifact | Creature),
                description="target artifact or creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if not isinstance(target, Artifact | Creature):
            return
        if not any(game.get_battlefield(player).contains(target) for player in game.players):
            return
        destroy(game, target)
        controller = self.controller
        if controller is not None:
            controller.life += 1
