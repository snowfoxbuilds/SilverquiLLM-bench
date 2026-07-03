"""Card implementation for Oracle's Restoration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class OraclesRestoration(Sorcery):
    """Oracle's Restoration."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Oracle's Restoration")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature)
                and getattr(obj, "controller", None) is self.controller,
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        chosen_targets = getattr(self, "chosen_targets", [])
        target = chosen_targets[0] if chosen_targets else None
        if (
            controller is None
            or not isinstance(target, Creature)
            or getattr(target, "controller", None) is not controller
            or not game.get_battlefield(controller).contains(target)
        ):
            return

        def _apply(_game: GameState) -> None:
            target.modified_power += 1
            target.modified_toughness += 1

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

        draw_card(game, controller)
        controller.life += 1
        controller.life_gained_this_turn = getattr(controller, "life_gained_this_turn", 0) + 1
        game.trigger_manager.fire_event(
            game,
            GainsLifeTriggeredEvent(player=controller, amount=1),
        )
