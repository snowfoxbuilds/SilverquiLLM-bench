"""Card implementation for Interjection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Interjection(Instant):
    """Interjection."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Interjection")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature gets +2/+2 and gains first strike until end of turn.",
        )
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
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if not isinstance(target, Creature):
            return
        controller = getattr(target, "controller", None)
        if controller is None or not game.get_battlefield(controller).contains(target):
            return

        def _apply_stats(game: GameState) -> None:  # noqa: ARG001
            target.modified_power += 2
            target.modified_toughness += 2

        def _apply_first_strike(game: GameState) -> None:  # noqa: ARG001
            target.keywords |= Keyword.FIRST_STRIKE

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_stats,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply_first_strike,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
