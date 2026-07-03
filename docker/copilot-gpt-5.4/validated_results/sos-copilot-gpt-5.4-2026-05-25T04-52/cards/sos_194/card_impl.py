"""Card implementation for Hardened Academic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, discard
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class HardenedAcademic(Creature):
    """Hardened Academic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hardened Academic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("subtypes", {"Bird", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def _target_requirement(self, controller: Any | None = None) -> TargetRequirement:
        locked_controller = self.controller if controller is None else controller
        return TargetRequirement(
            filter_fn=lambda obj, current_controller=locked_controller: (
                isinstance(obj, Creature)
                and current_controller is not None
                and getattr(obj, "controller", None) is current_controller
            ),
            description="target creature you control",
            zone=Zone.BATTLEFIELD,
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, card: Creature) -> bool:
            controller = getattr(card, "controller", None)
            if controller is None:
                return False
            hand = game.get_hand(controller).get_all()
            if not hand:
                return False
            try:
                chosen = controller.choose_card(hand, "Choose a card to discard")
            except Exception:
                chosen = hand[0]
            if chosen not in hand:
                chosen = hand[0]
            discard(game, controller, chosen)
            return True

        def _effect(game: GameState) -> None:
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.ABILITY,
                    apply=lambda _game: setattr(
                        source,
                        "keywords",
                        source.keywords | Keyword.LIFELINK,
                    ),
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Discard a card: This creature gains lifelink until end of turn.",
            )
        ]

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: GraveyardLeavesTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and bool(event.cards)
                and source.is_on_battlefield(g)
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(g: GameState, event: GraveyardLeavesTriggeredEvent) -> StackObject | None:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            requirement = source._target_requirement(current_controller)
            candidates = [
                permanent
                for permanent in g.get_battlefield(current_controller).get_all()
                if requirement.filter_fn(permanent)
            ]
            if not candidates:
                return None
            try:
                chosen = current_controller.choose_target([requirement], requirement)
            except Exception:
                chosen = candidates[0]
            if chosen not in candidates:
                chosen = candidates[0]

            def _resolve(game_at_resolution: GameState, *, target: Creature = chosen) -> None:
                if not target.is_on_battlefield(game_at_resolution):
                    return
                if not requirement.filter_fn(target):
                    return
                add_counter(game_at_resolution, target, "+1/+1")

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GraveyardLeavesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
