"""Card implementation for Encouraging Aviator // Jump."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Jump(Instant):
    """Prepared spell copy for Encouraging Aviator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Jump")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class EncouragingAviatorJump(Creature):
    """Encouraging Aviator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Encouraging Aviator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Bird", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def create_prepared_spell_copy(self) -> Instant:
        return Jump(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: AttacksTriggeredEvent) -> bool:  # noqa: ARG001
            return event.attacker is source or event.creature is source

        def _effect(game: GameState) -> None:  # noqa: ARG001
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
