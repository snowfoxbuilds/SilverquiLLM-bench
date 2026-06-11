"""Card implementation for Ambitious Augmenter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent, SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, create_token
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_fractal_with_counters(
    plus_one_counters: int,
    minus_one_counters: int,
    misc_counters: dict[str, int],
) -> Creature:
    token = Creature(
        name="Fractal",
        base_power=0,
        base_toughness=0,
        subtypes={"Fractal"},
    )
    token.colors = {Color.GREEN, Color.BLUE}  # type: ignore[attr-defined]
    token.plus_one_counters = plus_one_counters
    token._base_plus_one_counters = plus_one_counters
    token.minus_one_counters = minus_one_counters
    token._base_minus_one_counters = minus_one_counters
    token._counters = dict(misc_counters)
    token.snapshot_current_characteristics()
    return token


class AmbitiousAugmenter(Creature):
    """Ambitious Augmenter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ambitious Augmenter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault("subtypes", {"Turtle", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

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
                add_counter(g, source, "+1/+1")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_increment_condition,
                effect=_increment_effect,
                source=self,
                controller=controller,
            )
        )

        def _death_condition(_g: GameState, event: CreatureDiesTriggeredEvent) -> bool:
            if event.creature is not source:
                return False
            total_counters = (
                max(0, int(getattr(source, "plus_one_counters", 0)))
                + max(0, int(getattr(source, "minus_one_counters", 0)))
                + sum(max(0, int(amount)) for amount in getattr(source, "_counters", {}).values())
            )
            return total_counters > 0

        def _noop(_game: GameState) -> None:
            return

        def _death_stack_object(
            _g: GameState,
            event: CreatureDiesTriggeredEvent,
        ) -> StackObject | None:
            token_controller = event.controller or getattr(source, "controller", None)
            if token_controller is None:
                return None
            plus_one_counters = max(0, int(getattr(source, "plus_one_counters", 0)))
            minus_one_counters = max(0, int(getattr(source, "minus_one_counters", 0)))
            misc_counters = dict(getattr(source, "_counters", {}))
            total_counters = plus_one_counters + minus_one_counters + sum(
                max(0, int(amount)) for amount in misc_counters.values()
            )
            if total_counters <= 0:
                return None

            def _resolve(
                game_at_resolution: GameState,
                *,
                player=token_controller,
                plus=plus_one_counters,
                minus=minus_one_counters,
                extras=misc_counters,
            ) -> None:
                create_token(
                    game_at_resolution,
                    player,
                    _create_fractal_with_counters(plus, minus, extras),
                )

            return StackObject(
                source=source,
                controller=token_controller,
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CreatureDiesTriggeredEvent,
                condition=_death_condition,
                effect=_noop,
                source=self,
                controller=controller,
                create_stack_object=_death_stack_object,
            )
        )
