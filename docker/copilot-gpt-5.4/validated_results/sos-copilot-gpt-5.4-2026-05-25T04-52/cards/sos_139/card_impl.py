"""Card implementation for Additive Evolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Enchantment
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.events import (
    BeginningOfCombatTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import add_counter, create_token
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_fractal_token(counter_count: int) -> Creature:
    token = Creature(
        name="Fractal",
        base_power=0,
        base_toughness=0,
        subtypes={"Fractal"},
    )
    token.colors = {Color.GREEN, Color.BLUE}  # type: ignore[attr-defined]
    token.plus_one_counters = counter_count
    token._base_plus_one_counters = counter_count
    token.snapshot_current_characteristics()
    return token


class AdditiveEvolution(Enchantment):
    """Additive Evolution."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Additive Evolution")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _create_etb_stack_object(current_controller: object | None) -> StackObject | None:
            if current_controller is None:
                return None

            def _resolve(game_at_resolution: GameState, *, player=current_controller) -> None:
                create_token(game_at_resolution, player, _create_fractal_token(3))

            return StackObject(
                source=source,
                controller=current_controller,
                on_resolve=_resolve,
            )

        if getattr(source, "_registering_after_enter_battlefield", False):
            stack_object = _create_etb_stack_object(getattr(source, "controller", None))
            if stack_object is not None:
                game.stack.push(stack_object)

        def _etb_condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return source.is_on_battlefield(g) and event.permanent is source

        def _noop(_game: GameState) -> None:
            return

        def _etb_stack_object(
            _game: GameState,
            _event: EntersBattlefieldTriggeredEvent,
        ) -> StackObject | None:
            return _create_etb_stack_object(getattr(source, "controller", None))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_etb_condition,
                effect=_noop,
                source=self,
                controller=controller,
                create_stack_object=_etb_stack_object,
            )
        )

        def _combat_condition(g: GameState, event: BeginningOfCombatTriggeredEvent) -> bool:  # noqa: ARG001
            return source.is_on_battlefield(g) and getattr(source, "controller", None) is g.active_player

        def _combat_stack_object(
            g: GameState,
            _event: BeginningOfCombatTriggeredEvent,
        ) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            requirement = TargetRequirement(
                filter_fn=lambda obj, player=current_controller: isinstance(obj, Creature)
                and getattr(obj, "controller", None) is player,
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
            candidates = [
                permanent
                for permanent in g.get_battlefield(current_controller).get_all()
                if requirement.filter_fn(permanent)
            ]
            if not candidates:
                return None
            try:
                chosen = current_controller.choose_target(candidates, requirement)
            except Exception:
                chosen = candidates[0]
            if chosen not in candidates:
                return None

            def _resolve(game_at_resolution: GameState, *, target=chosen, player=current_controller) -> None:
                if getattr(target, "controller", None) is not player:
                    return
                if not any(game_at_resolution.get_battlefield(p).contains(target) for p in game_at_resolution.players):
                    return
                add_counter(game_at_resolution, target, "+1/+1")
                game_at_resolution.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.ABILITY,
                        apply=lambda _g, creature=target: setattr(
                            creature,
                            "keywords",
                            creature.keywords | Keyword.VIGILANCE,
                        ),
                        duration=DURATION_END_OF_TURN,
                    )
                )
                game_at_resolution.effect_manager.apply_all(game_at_resolution)

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfCombatTriggeredEvent,
                condition=_combat_condition,
                effect=_noop,
                source=self,
                controller=controller,
                create_stack_object=_combat_stack_object,
            )
        )
