"""Card implementation for Scathing Shadelock // Venomous Words."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import BeginningOfFirstMainPhaseTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class VenomousWords(Sorcery):
    """Prepared spell copy for Scathing Shadelock."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Venomous Words")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("rules_text", "Prepared spell copy.")
        super().__init__(**kwargs)


class ScathingShadelockVenomousWords(Creature):
    """Scathing Shadelock."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scathing Shadelock")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("subtypes", {"Snake", "Warlock"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "At the beginning of your first main phase, this creature becomes prepared.",
        )
        super().__init__(**kwargs)

    def create_prepared_spell_copy(self) -> Sorcery:
        return VenomousWords(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: BeginningOfFirstMainPhaseTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
            )

        def _effect(_game: GameState) -> None:
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfFirstMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
