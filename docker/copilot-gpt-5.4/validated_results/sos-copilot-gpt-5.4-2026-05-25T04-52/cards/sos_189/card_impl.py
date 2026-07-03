"""Card implementation for Fractal Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, tap
from benchmarks.sos.workspace.engine.protection import get_illegal_target_reason
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class FractalMascot(Creature):
    """Fractal Mascot."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{U}"))
        kwargs.setdefault("subtypes", {"Fractal", "Elk"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        super().__init__(**kwargs)

    def _target_requirement(self, controller: Any | None = None) -> TargetRequirement:
        locked_controller = self.controller if controller is None else controller
        return TargetRequirement(
            filter_fn=lambda obj, current_controller=locked_controller: (
                isinstance(obj, Creature)
                and current_controller is not None
                and getattr(obj, "controller", None) is not current_controller
            ),
            description="target creature an opponent controls",
            zone=Zone.BATTLEFIELD,
        )

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return (
                source.is_on_battlefield(g)
                and (event.permanent is source or event.creature is source or event.card is source)
            )

        def _noop(_game: GameState) -> None:
            return

        def _create_etb_stack_object(g: GameState) -> StackObject | None:
            locked_controller = getattr(source, "controller", None)
            if locked_controller is None:
                return None

            requirement = source._target_requirement(locked_controller)
            candidates = [
                permanent
                for player in g.players
                for permanent in g.get_battlefield(player).get_all()
                if requirement.filter_fn(permanent)
                and get_illegal_target_reason(permanent, source) is None
            ]
            if not candidates:
                return None

            try:
                chosen = locked_controller.choose_target([requirement], requirement)
            except Exception:
                chosen = None
            if chosen not in candidates:
                chosen = candidates[0]

            def _resolve(
                resolution_game: GameState,
                *,
                target: Creature = chosen,
                target_requirement: TargetRequirement = requirement,
            ) -> None:
                if not target.is_on_battlefield(resolution_game):
                    return
                if not target_requirement.filter_fn(target):
                    return
                if get_illegal_target_reason(target, source) is not None:
                    return
                tap(resolution_game, target)
                add_counter(resolution_game, target, "stun")

            return StackObject(
                source=source,
                controller=locked_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        if getattr(source, "_registering_after_enter_battlefield", False):
            stack_object = _create_etb_stack_object(game)
            if stack_object is not None:
                game.stack.push(stack_object)

        def _create_stack_object(
            g: GameState,
            _event: EntersBattlefieldTriggeredEvent,
        ) -> StackObject | None:
            return _create_etb_stack_object(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_noop,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
