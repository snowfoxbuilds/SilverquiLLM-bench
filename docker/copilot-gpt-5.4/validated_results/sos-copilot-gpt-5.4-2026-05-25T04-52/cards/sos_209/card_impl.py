"""Card implementation for Pest Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PestMascot(Creature):
    """Pest Mascot."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        kwargs.setdefault("subtypes", {"Pest", "Ape"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: GainsLifeTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
            )

        def _effect(g: GameState) -> None:
            if source.is_on_battlefield(g):
                add_counter(g, source, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GainsLifeTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
