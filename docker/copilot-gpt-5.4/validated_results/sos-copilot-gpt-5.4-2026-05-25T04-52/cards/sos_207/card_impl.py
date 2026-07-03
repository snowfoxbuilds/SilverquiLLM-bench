"""Card implementation for Old-Growth Educator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class OldGrowthEducator(Creature):
    """Old-Growth Educator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Old-Growth Educator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{G}"))
        kwargs.setdefault("subtypes", {"Treefolk", "Druid"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE | Keyword.REACH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and getattr(event, "permanent", None) is source
                and getattr(event, "controller", None) is current_controller
                and source.is_on_battlefield(g)
                and getattr(current_controller, "life_gained_this_turn", 0) > 0
            )

        def _effect(g: GameState) -> None:
            if source.is_on_battlefield(g):
                add_counter(g, source, "+1/+1", 2)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
