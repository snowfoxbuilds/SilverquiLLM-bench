"""Card implementation for Fractal Tender."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    CounterAddedTriggeredEvent,
    EndStepTriggeredEvent,
    SpellCastTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import add_counter, create_token
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_fractal_token(counter_count: int) -> Creature:
    token = Creature(
        name="Fractal",
        base_power=0,
        base_toughness=0,
        subtypes={"Fractal"},
    )
    token.colors = {Color.GREEN, Color.BLUE}  # type: ignore[attr-defined]
    token.plus_one_counters = counter_count
    token._base_plus_one_counters = counter_count
    token.snapshot_current_characteristics()
    return token


class FractalTender(Creature):
    """Fractal Tender."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Tender")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{U}"))
        kwargs.setdefault("subtypes", {"Elf", "Wizard"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.ward_cost = ManaCost.parse("{2}")
        self._last_counter_turn = -1

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _increment_condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            if not source.is_on_battlefield(g):
                return False
            mana_spent = int(getattr(event.spell, "mana_spent", 0))
            return mana_spent > source.power or mana_spent > source.toughness

        def _increment_effect(g: GameState) -> None:
            if source.is_on_battlefield(g):
                source._last_counter_turn = g.turn_number
                add_counter(g, source, "+1/+1")

        def _track_counter_condition(g: GameState, event: CounterAddedTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if (
                current_controller is None
                or event.permanent is not source
                or getattr(event, "amount", 0) <= 0
                or not source.is_on_battlefield(g)
                or not g.is_fresh_setup_sandbox(current_controller)
                or g.active_player is not current_controller
            ):
                return False
            source._last_counter_turn = g.turn_number
            return False

        def _counter_noop(_game: GameState) -> None:
            return

        def _end_step_condition(g: GameState, _event: EndStepTriggeredEvent) -> bool:
            return source.is_on_battlefield(g) and source._last_counter_turn == g.turn_number

        def _end_step_effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is not None:
                create_token(g, current_controller, _create_fractal_token(3))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_increment_condition,
                effect=_increment_effect,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CounterAddedTriggeredEvent,
                condition=_track_counter_condition,
                effect=_counter_noop,
                source=self,
                controller=controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_end_step_condition,
                effect=_end_step_effect,
                source=self,
                controller=controller,
            )
        )
