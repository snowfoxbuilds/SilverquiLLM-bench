"""Card implementation for Colorstorm Stallion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ColorstormStallion(Creature):
    """Colorstorm Stallion."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Colorstorm Stallion")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{R}"))
        kwargs.setdefault("subtypes", {"Elemental", "Horse"})
        kwargs.setdefault("keywords", Keyword.WARD | Keyword.HASTE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.ward_cost = ManaCost.parse("{1}")

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
                and source.is_on_battlefield(g)
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(_game: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            if current_controller is None or spell is None:
                return None
            should_copy = int(getattr(spell, "mana_spent", 0)) >= 5

            def _resolve(game_at_resolution: GameState) -> None:
                if not source.is_on_battlefield(game_at_resolution):
                    return

                def _apply_bonus(_g: GameState, *, creature: Creature = source) -> None:
                    if creature.is_on_battlefield(_g):
                        creature.modified_power += 1
                        creature.modified_toughness += 1

                game_at_resolution.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.POWER_TOUGHNESS,
                        sublayer=SubLayer.MODIFY_PT,
                        apply=_apply_bonus,
                        duration=DURATION_END_OF_TURN,
                    )
                )
                game_at_resolution.effect_manager.apply_all(game_at_resolution)

                if not should_copy:
                    return
                token = ColorstormStallion(owner=current_controller, controller=current_controller)
                create_token(game_at_resolution, current_controller, token)

            return StackObject(
                source=source,
                controller=current_controller,
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
