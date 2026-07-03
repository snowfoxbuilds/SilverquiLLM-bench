"""Card implementation for Shopkeeper's Bane."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent, GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ShopkeepersBane(Creature):
    """Shopkeeper's Bane."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Shopkeeper's Bane")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Badger", "Pest"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_game: GameState, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            current_controller.life += 2
            current_controller.life_gained_this_turn = (
                getattr(current_controller, "life_gained_this_turn", 0) + 2
            )
            g.trigger_manager.fire_event(
                g,
                GainsLifeTriggeredEvent(player=current_controller, amount=2),
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
