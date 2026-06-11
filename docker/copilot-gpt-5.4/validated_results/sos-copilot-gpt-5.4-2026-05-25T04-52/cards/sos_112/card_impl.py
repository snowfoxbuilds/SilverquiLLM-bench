"""Card implementation for Duel Tactics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DuelTactics(Sorcery):
    """Duel Tactics."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Duel Tactics")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{1}{R}")

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0]
        if not isinstance(target, Creature):
            return
        controller = getattr(target, "controller", None)
        if controller is None or not game.get_battlefield(controller).contains(target):
            return
        deal_damage(game, self, target, 1)
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.TEXT,
                apply=lambda _game, *, creature=target: setattr(creature, "_cant_block", True),
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
