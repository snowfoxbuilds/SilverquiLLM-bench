"""Card implementation for Masterful Flourish."""

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


class MasterfulFlourish(Instant):
    """Masterful Flourish."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Masterful Flourish")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature you control gets +1/+0 and gains indestructible until end of turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj, _controller=controller: (
                    isinstance(obj, Creature) and getattr(obj, "controller", None) is _controller
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        chosen = getattr(self, "chosen_targets", [])
        target = chosen[0] if chosen else None
        controller = self.controller
        if not isinstance(target, Creature) or controller is None:
            return
        if not target.is_on_battlefield(game) or target.controller is not controller:
            return

        def _apply_power(_game: GameState) -> None:
            target.modified_power += 1

        def _apply_indestructible(_game: GameState) -> None:
            target.keywords |= Keyword.INDESTRUCTIBLE

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_power,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply_indestructible,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
