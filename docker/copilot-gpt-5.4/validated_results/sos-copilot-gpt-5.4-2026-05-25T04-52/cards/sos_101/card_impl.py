"""Card implementation for Sneering Shadewriter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    EntersBattlefieldTriggeredEvent,
    GainsLifeTriggeredEvent,
    LosesLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SneeringShadewriter(Creature):
    """Sneering Shadewriter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sneering Shadewriter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, each opponent loses 2 life and you gain 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            for player in g.players:
                if player is current_controller:
                    continue
                player.life -= 2
                g.trigger_manager.fire_event(
                    g,
                    LosesLifeTriggeredEvent(player=player, amount=2),
                )
            current_controller.life += 2
            current_controller.life_gained_this_turn = (
                getattr(current_controller, "life_gained_this_turn", 0) + 2
            )
            g.trigger_manager.fire_event(
                g,
                GainsLifeTriggeredEvent(player=current_controller, amount=2),
            )

        if getattr(source, "_registering_after_enter_battlefield", False):
            game.stack.push(
                StackObject(
                    source=self,
                    controller=controller,
                    on_resolve=_effect,
                )
            )

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.permanent is source
                and g.get_battlefield(current_controller).contains(source)
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
