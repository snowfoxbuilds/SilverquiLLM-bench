"""Card implementation for Owlin Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class OwlinHistorian(Creature):
    """Owlin Historian."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Owlin Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Bird", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, surveil 1.\nWhenever one or more cards leave "
            "your graveyard, this creature gets +1/+1 until end of turn.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        if len(library) == 0:
            return
        top_card = library.top(1)[0]
        if controller.choose_yes_no("Put the top card of your library into your graveyard?"):
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.GRAVEYARD)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: GraveyardLeavesTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(game)
            )

        def _effect(game: GameState) -> None:
            def _apply(game: GameState) -> None:  # noqa: ARG001
                source.modified_power += 1
                source.modified_toughness += 1

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

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GraveyardLeavesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
