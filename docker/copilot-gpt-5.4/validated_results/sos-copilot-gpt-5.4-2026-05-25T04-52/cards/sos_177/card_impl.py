"""Card implementation for Bogwater Lumaret."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    EntersBattlefieldTriggeredEvent,
    GainsLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class BogwaterLumaret(Creature):
    """Bogwater Lumaret."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bogwater Lumaret")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{G}"))
        kwargs.setdefault("subtypes", {"Spirit", "Frog"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            entering_permanent = getattr(event, "permanent", None)
            return (
                current_controller is not None
                and event.controller is current_controller
                and isinstance(entering_permanent, Creature)
                and source.is_on_battlefield(g)
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            current_controller.life += 1
            current_controller.life_gained_this_turn = (
                getattr(current_controller, "life_gained_this_turn", 0) + 1
            )
            g.trigger_manager.fire_event(
                g,
                GainsLifeTriggeredEvent(player=current_controller, amount=1),
            )

        if getattr(source, "_registering_after_enter_battlefield", False):
            game.stack.push(
                StackObject(
                    source=self,
                    controller=controller,
                    on_resolve=_effect,
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
