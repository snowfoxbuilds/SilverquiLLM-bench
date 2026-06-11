"""Card implementation for Berta, Wise Extrapolator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.events import CounterAddedTriggeredEvent, SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, create_token
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, ManaCost, ManaType, Supertype

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


class BertaWiseExtrapolator(Creature):
    """Berta, Wise Extrapolator."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Berta, Wise Extrapolator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Frog", "Druid"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
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

        def _mana_condition(g: GameState, event: CounterAddedTriggeredEvent) -> bool:
            return (
                getattr(event, "permanent", None) is source
                and getattr(event, "counter_type", None) == "+1/+1"
                and getattr(event, "amount", 0) > 0
                and source.is_on_battlefield(g)
            )

        def _mana_effect(_game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            color_choices = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            try:
                chosen = current_controller.choose(
                    color_choices,
                    "Choose a color of mana for Berta, Wise Extrapolator",
                )
            except Exception:
                chosen = ManaType.GREEN
            if chosen not in color_choices:
                chosen = ManaType.GREEN
            current_controller.mana_pool.add(chosen, 1)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CounterAddedTriggeredEvent,
                condition=_mana_condition,
                effect=_mana_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, card: Creature) -> bool:  # noqa: ARG001
            controller = source.controller
            if controller is None or card.is_tapped:
                return False
            x_value = max(0, int(getattr(source, "x_value", 0)))
            mana_cost = ManaCost(generic=x_value)
            if not controller.mana_pool.can_pay(mana_cost):
                return False
            controller.mana_pool.pay(mana_cost)
            card.is_tapped = True
            return True

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            x_value = max(0, int(getattr(source, "x_value", 0)))
            create_token(game, controller, _create_fractal_token(x_value))

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{X}, {T}: Create a green and blue Fractal token.",
            )
        ]
