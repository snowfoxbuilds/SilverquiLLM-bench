"""Card implementation for Last Gasp."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class LastGasp(Instant):
    """Last Gasp."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Last Gasp")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("rules_text", "Target creature gets -3/-3 until end of turn.")
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
        chosen = getattr(self, "chosen_targets", [])
        target = chosen[0] if chosen else None
        if not isinstance(target, Creature):
            return

        controller = getattr(target, "controller", None)
        if controller is None or not game.get_battlefield(controller).contains(target):
            return

        def _apply(_game: GameState) -> None:
            target.modified_power -= 3
            target.modified_toughness -= 3

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
