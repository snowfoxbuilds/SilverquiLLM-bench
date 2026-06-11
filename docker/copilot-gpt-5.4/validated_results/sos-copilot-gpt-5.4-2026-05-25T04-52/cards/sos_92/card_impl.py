"""Card implementation for Poisoner's Apprentice."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.protection import get_illegal_target_reason
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PoisonersApprentice(Creature):
    """Poisoner's Apprentice."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Poisoner's Apprentice")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Orc", "Warlock"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Infusion — When this creature enters, target creature an opponent controls gets "
            "-4/-4 until end of turn if you gained life this turn.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.permanent is source
                and g.get_battlefield(current_controller).contains(source)
                and getattr(current_controller, "life_gained_this_turn", 0) > 0
            )

        def _effect(_g: GameState) -> None:
            return

        def _create_stack_object(
            g: GameState,
            event: EntersBattlefieldTriggeredEvent,  # noqa: ARG001
        ) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            target_spec = TargetRequirement(
                filter_fn=lambda obj, _source=source, _game=g: (
                    isinstance(obj, Creature)
                    and obj.is_on_battlefield(_game)
                    and getattr(obj, "controller", None) is not getattr(_source, "controller", None)
                ),
                description="target creature an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
            candidates = [
                permanent
                for player in g.players
                if player is not current_controller
                for permanent in g.get_battlefield(player).get_all()
                if target_spec.filter_fn(permanent)
                and get_illegal_target_reason(permanent, source) is None
            ]
            if not candidates:
                return None
            try:
                chosen = current_controller.choose_target(
                    [target_spec],
                    target_spec,
                )
            except Exception:
                chosen = candidates[0]
            if chosen not in candidates:
                chosen = candidates[0]

            def _resolve(resolution_game: GameState, *, target: Creature = chosen) -> None:
                if not target_spec.filter_fn(target):
                    return
                if get_illegal_target_reason(target, source) is not None:
                    return

                def _apply(_game: GameState, *, affected: Creature = target) -> None:
                    affected.modified_power -= 4
                    affected.modified_toughness -= 4

                resolution_game.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.POWER_TOUGHNESS,
                        sublayer=SubLayer.MODIFY_PT,
                        apply=_apply,
                        duration=DURATION_END_OF_TURN,
                    )
                )
                resolution_game.effect_manager.apply_all(resolution_game)

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
