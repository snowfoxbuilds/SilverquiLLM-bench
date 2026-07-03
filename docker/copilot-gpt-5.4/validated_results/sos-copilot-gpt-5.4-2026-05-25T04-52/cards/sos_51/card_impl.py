"""Card implementation for Fractalize."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import Color, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Fractalize(Instant):
    """Fractalize."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractalize")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Until end of turn, target creature becomes a green and blue Fractal "
            "with base power and toughness each equal to X plus 1.",
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
        if not any(game.get_battlefield(player).contains(target) for player in game.players):
            return

        if (
            hasattr(target, "colors")
            and not getattr(target, "_has_original_colors_attr", False)
            and not game.effect_manager.effects
        ):
            target._has_original_colors_attr = True
            target._original_colors = set(target.colors)

        x_value = getattr(self, "x_value", 0)

        def _apply_type(game: GameState) -> None:  # noqa: ARG001
            target.subtypes = {"Fractal"}

        def _apply_color(game: GameState) -> None:  # noqa: ARG001
            target.colors = {Color.GREEN, Color.BLUE}

        def _apply_pt(game: GameState) -> None:  # noqa: ARG001
            target.modified_power = x_value + 1
            target.modified_toughness = x_value + 1

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.TYPE,
                apply=_apply_type,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.COLOR,
                apply=_apply_color,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.SET_PT,
                apply=_apply_pt,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
