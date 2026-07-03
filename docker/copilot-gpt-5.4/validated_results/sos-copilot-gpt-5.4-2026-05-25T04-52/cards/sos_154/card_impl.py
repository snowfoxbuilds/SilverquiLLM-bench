"""Card implementation for Mindful Biomancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MindfulBiomancer(Creature):
    """Mindful Biomancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mindful Biomancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Dryad", "Druid"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self._pump_turn_number: int | None = None

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.permanent is source
                and g.get_battlefield(current_controller).contains(source)
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            current_controller.life += 1
            current_controller.life_gained_this_turn = (
                getattr(current_controller, "life_gained_this_turn", 0) + 1
            )
            g.trigger_manager.fire_event(
                g,
                GainsLifeTriggeredEvent(player=current_controller, amount=1),
            )

        if getattr(source, "_registering_after_enter_battlefield", False):
            game.stack.push(
                StackObject(
                    source=self,
                    controller=controller,
                    on_resolve=_effect,
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, card: MindfulBiomancer) -> bool:
            controller = card.controller
            if controller is None:
                return False
            if source._pump_turn_number == game.turn_number:
                return False
            mana_cost = ManaCost.parse("{2}{G}")
            if not controller.mana_pool.can_pay(mana_cost):
                return False
            controller.mana_pool.pay(mana_cost)
            source._pump_turn_number = game.turn_number
            return True

        def _effect(game: GameState) -> None:
            def _apply(_game: GameState) -> None:
                source.modified_power += 2
                source.modified_toughness += 2

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{2}{G}: This creature gets +2/+2 until end of turn. Activate only once each turn.",
            )
        ]
