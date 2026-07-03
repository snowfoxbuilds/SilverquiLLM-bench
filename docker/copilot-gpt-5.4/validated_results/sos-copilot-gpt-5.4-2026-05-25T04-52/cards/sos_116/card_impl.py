"""Card implementation for Garrison Excavator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_spirit_token() -> Creature:
    token = Creature(
        name="Spirit",
        subtypes={"Spirit"},
        base_power=2,
        base_toughness=2,
    )
    token.colors = {Color.RED, Color.WHITE}  # type: ignore[attr-defined]
    return token


class GarrisonExcavator(Creature):
    """Garrison Excavator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Garrison Excavator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("subtypes", {"Orc", "Sorcerer"})
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: GraveyardLeavesTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and bool(event.cards)
                and source.is_on_battlefield(game)
            )

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(game):
                return
            create_token(game, current_controller, _create_spirit_token())

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GraveyardLeavesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
