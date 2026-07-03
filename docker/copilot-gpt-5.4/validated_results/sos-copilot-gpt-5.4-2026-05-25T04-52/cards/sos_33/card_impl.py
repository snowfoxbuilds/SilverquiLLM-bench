"""Card implementation for Spiritcall Enthusiast // Scrollboost."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Scrollboost(Sorcery):
    """Prepared spell copy for Spiritcall Enthusiast."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scrollboost")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)


class SpiritcallEnthusiastScrollboost(Creature):
    """Spiritcall Enthusiast."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spiritcall Enthusiast")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Whenever one or more tokens you control enter, this creature becomes prepared.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            permanent = getattr(event, "permanent", None)
            return (
                current_controller is not None
                and event.controller is current_controller
                and permanent is not None
                and getattr(permanent, "is_token", False)
            )

        def _effect(game: GameState) -> None:  # noqa: ARG001
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def create_prepared_spell_copy(self) -> Sorcery:
        return Scrollboost(owner=self.owner, controller=self.controller)
