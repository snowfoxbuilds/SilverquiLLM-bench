"""Card implementation for Cuboid Colony."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class CuboidColony(Creature):
    """Cuboid Colony."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cuboid Colony")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{U}"))
        kwargs.setdefault("subtypes", {"Insect"})
        kwargs.setdefault("keywords", Keyword.FLASH | Keyword.FLYING | Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            mana_spent = int(getattr(getattr(event, "spell", None), "mana_spent", 0))
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
                and (mana_spent > source.power or mana_spent > source.toughness)
            )

        def _effect(_g: GameState) -> None:
            return

        def _create_stack_object(_g: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:
            mana_spent = int(getattr(getattr(event, "spell", None), "mana_spent", 0))

            def _resolve(game_at_resolution: GameState, *, spent: int = mana_spent) -> None:
                if not source.is_on_battlefield(game_at_resolution):
                    return
                if spent <= source.power and spent <= source.toughness:
                    return
                add_counter(game_at_resolution, source, "+1/+1")

            return StackObject(
                source=source,
                controller=controller,
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
