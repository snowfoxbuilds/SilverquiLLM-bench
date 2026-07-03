"""Card implementation for Kirol, History Buff // Pack a Punch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PackAPunch(Sorcery):
    """Prepared spell copy for Kirol, History Buff."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pack a Punch")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}{W}"))
        super().__init__(**kwargs)


class KirolHistoryBuffPackAPunch(Creature):
    """Kirol, History Buff."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kirol, History Buff")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Vampire", "Cleric"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def create_prepared_spell_copy(self) -> Sorcery:
        return PackAPunch(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: GraveyardLeavesTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and bool(event.cards)
                and source.is_on_battlefield(g)
            )

        def _effect(_game: GameState) -> None:
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GraveyardLeavesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
