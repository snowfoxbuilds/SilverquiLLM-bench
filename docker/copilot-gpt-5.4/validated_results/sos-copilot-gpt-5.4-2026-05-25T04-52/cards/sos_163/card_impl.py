"""Card implementation for Tenured Concocter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import BecomesTargetTriggeredEvent
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TenuredConcocter(Creature):
    """Tenured Concocter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tenured Concocter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}"))
        kwargs.setdefault("subtypes", {"Troll", "Druid"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)
        self._infusion_effect: ContinuousEffect | None = None

    def register_triggers(self, game: GameState) -> None:
        self.apply_continuous_effect(game)
        if any(
            trigger.event_type is BecomesTargetTriggeredEvent
            for trigger in game.trigger_manager.get_triggers_for_source(self)
        ):
            return

        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: BecomesTargetTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and source.is_on_battlefield(g)
                and event.target is source
                and event.controller is not None
                and event.controller is not current_controller
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            try:
                should_draw = current_controller.choose_yes_no("Draw a card?")
            except Exception:
                should_draw = False
            if should_draw:
                draw_card(g, current_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BecomesTargetTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def apply_continuous_effect(self, game: GameState) -> list[ContinuousEffect]:
        existing = game.effect_manager.get_effects_by_source(self)
        if existing:
            return existing

        source = self

        def _apply(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if (
                current_controller is None
                or not source.is_on_battlefield(g)
                or getattr(current_controller, "life_gained_this_turn", 0) <= 0
            ):
                return
            source.modified_power += 2

        effect = game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
        )
        self._infusion_effect = effect
        return [effect]
