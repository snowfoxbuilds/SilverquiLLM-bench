"""Card implementation for Chase Inspiration."""

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


class ChaseInspiration(Instant):
    """Chase Inspiration."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chase Inspiration")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj, _controller=controller: (
                    isinstance(obj, Creature)
                    and getattr(obj, "controller", None) is _controller
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

        def _apply_toughness(_game: GameState) -> None:
            target.modified_toughness += 3

        def _apply_hexproof(_game: GameState) -> None:
            target.keywords |= Keyword.HEXPROOF

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_toughness,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply_hexproof,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
