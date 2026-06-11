"""Card implementation for Pensive Professor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import CounterAddedTriggeredEvent, SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class PensiveProfessor(Creature):
    """Pensive Professor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pensive Professor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Increment\nWhenever one or more +1/+1 counters are put on this creature, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _increment_condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            if not source.is_on_battlefield(game):
                return False
            mana_spent = int(getattr(event.spell, "mana_spent", 0))
            return mana_spent > source.power or mana_spent > source.toughness

        def _increment_effect(game: GameState) -> None:
            if not source.is_on_battlefield(game):
                return
            add_counter(game, source, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_increment_condition,
                effect=_increment_effect,
                source=self,
                controller=controller,
            )
        )

        def _draw_condition(game: GameState, event: CounterAddedTriggeredEvent) -> bool:  # noqa: ARG001
            return (
                getattr(event, "permanent", None) is source
                and getattr(event, "counter_type", None) == "+1/+1"
                and getattr(event, "amount", 0) > 0
                and source.is_on_battlefield(game)
            )

        def _draw_effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(game):
                return
            draw_card(game, current_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CounterAddedTriggeredEvent,
                condition=_draw_condition,
                effect=_draw_effect,
                source=self,
                controller=controller,
            )
        )
