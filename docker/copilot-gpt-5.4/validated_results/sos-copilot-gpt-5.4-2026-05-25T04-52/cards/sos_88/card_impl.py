"""Card implementation for Leech Collector // Bloodletting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Bloodletting(Sorcery):
    """Prepared spell copy for Leech Collector."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bloodletting")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)


class LeechCollectorBloodletting(Creature):
    """Leech Collector."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Leech Collector")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Human", "Warlock"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever you gain life for the first time each turn, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self._last_prepared_turn_number: int | None = None

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: GainsLifeTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            if source._last_prepared_turn_number == game.turn_number:
                return False
            source._last_prepared_turn_number = game.turn_number
            return True

        def _effect(game: GameState) -> None:
            if not source.is_on_battlefield(game):
                return
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GainsLifeTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def create_prepared_spell_copy(self) -> Sorcery:
        return Bloodletting(owner=self.owner, controller=self.controller)
