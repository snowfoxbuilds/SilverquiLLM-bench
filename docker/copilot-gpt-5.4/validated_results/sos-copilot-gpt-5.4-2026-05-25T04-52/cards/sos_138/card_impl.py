"""Card implementation for Aberrant Manawurm."""

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
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AberrantManawurm(Creature):
    """Aberrant Manawurm."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Aberrant Manawurm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("subtypes", {"Wurm"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
                and spell is not None
                and bool(getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(_game: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            bonus = max(0, int(getattr(event.spell, "mana_spent", 0)))

            def _resolve(game_at_resolution: GameState, *, amount: int = bonus) -> None:
                if amount <= 0 or not source.is_on_battlefield(game_at_resolution):
                    return
                game_at_resolution.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.POWER_TOUGHNESS,
                        sublayer=SubLayer.MODIFY_PT,
                        apply=lambda _g, creature=source, power_bonus=amount: setattr(
                            creature,
                            "modified_power",
                            creature.modified_power + power_bonus,
                        ),
                        duration=DURATION_END_OF_TURN,
                    )
                )
                game_at_resolution.effect_manager.apply_all(game_at_resolution)

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
