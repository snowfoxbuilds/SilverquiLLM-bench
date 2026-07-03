"""Card implementation for Lumaret's Favor."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.stack import StackObject, copy_spell
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class LumaretsFavor(Instant):
    """Lumaret's Favor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lumaret's Favor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_cast_to_stack(self, game: GameState, stack_obj: StackObject) -> None:
        controller = self.controller
        if controller is None or getattr(controller, "life_gained_this_turn", 0) <= 0:
            return

        choose_new_targets = controller.choose_yes_no(
            f"Choose new targets for the copy of {self.name}?"
        )
        new_targets = None
        if choose_new_targets:
            copied_spell = copy(self)
            copied_spell.controller = controller
            copied_spell.owner = self.owner
            target_specs = copied_spell.get_targets(game)
            new_targets = list(stack_obj.targets)
            for index, spec in enumerate(target_specs):
                try:
                    chosen = controller.choose_target(target_specs, spec)
                except Exception:
                    continue
                if chosen is None or not spec.filter_fn(chosen):
                    continue
                if index < len(new_targets):
                    new_targets[index] = chosen
                else:
                    new_targets.append(chosen)

        game.stack.push(copy_spell(game, stack_obj, controller, new_targets))

    def on_resolve(self, game: GameState) -> None:
        chosen_targets = getattr(self, "chosen_targets", [])
        target = chosen_targets[0] if chosen_targets else None
        target_controller = getattr(target, "controller", None)
        if (
            not isinstance(target, Creature)
            or target_controller is None
            or not game.get_battlefield(target_controller).contains(target)
        ):
            return

        def _apply(_game: GameState) -> None:
            target.modified_power += 2
            target.modified_toughness += 4

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
