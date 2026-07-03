"""Card implementation for Abstract Paintmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import BeginningOfFirstMainPhaseTriggeredEvent
from benchmarks.sos.workspace.engine.mana import instant_or_sorcery_spell_only_restriction
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AbstractPaintmage(Creature):
    """Abstract Paintmage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abstract Paintmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}{U/R}{R}"))
        kwargs.setdefault("subtypes", {"Djinn", "Sorcerer"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player
        restriction = instant_or_sorcery_spell_only_restriction()

        def _condition(g: GameState, event: BeginningOfFirstMainPhaseTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
            )

        def _effect(_game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            current_controller.mana_pool.add(ManaType.BLUE, 1, restriction=restriction)
            current_controller.mana_pool.add(ManaType.RED, 1, restriction=restriction)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfFirstMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
