"""Card implementation for Tester of the Tangential."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import BeginningOfCombatTriggeredEvent, SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter, remove_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TesterOfTheTangential(Creature):
    """Tester of the Tangential."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tester of the Tangential")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Djinn", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Increment\nAt the beginning of combat on your turn, you may pay {X}. "
            "When you do, move X +1/+1 counters from this creature onto another target creature.",
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
            if source.is_on_battlefield(game):
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

        def _combat_condition(game: GameState, event: BeginningOfCombatTriggeredEvent) -> bool:  # noqa: ARG001
            return (
                getattr(source, "controller", None) is game.active_player
                and source.is_on_battlefield(game)
                and source.plus_one_counters > 0
            )

        def _combat_effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(game):
                return
            max_x = source.plus_one_counters
            x_value = current_controller.choose(
                list(range(max_x + 1)),
                "Choose X for Tester of the Tangential",
            )
            if not isinstance(x_value, int) or x_value <= 0:
                return
            x_value = min(x_value, max_x)
            payment = ManaCost(generic=x_value)
            if not current_controller.mana_pool.can_pay(payment):
                return
            current_controller.mana_pool.pay(payment)

            requirement = TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature) and obj is not source,
                description="another target creature",
                zone=Zone.BATTLEFIELD,
            )
            candidates = [
                permanent
                for player in game.players
                for permanent in game.get_battlefield(player).get_all()
                if requirement.filter_fn(permanent)
            ]
            if not candidates:
                return
            target = current_controller.choose_target(
                candidates,
                requirement,
            )
            if not isinstance(target, Creature) or target is source:
                return
            if not any(game.get_battlefield(player).contains(target) for player in game.players):
                return

            moved = min(x_value, source.plus_one_counters)
            if moved <= 0:
                return
            remove_counter(game, source, "+1/+1", moved)
            add_counter(game, target, "+1/+1", moved)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfCombatTriggeredEvent,
                condition=_combat_condition,
                effect=_combat_effect,
                source=self,
                controller=controller,
            )
        )
