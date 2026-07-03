"""Card implementation for Living History."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Enchantment
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, ManaCost

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
    token.snapshot_current_characteristics()
    return token


class LivingHistory(Enchantment):
    """Living History."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Living History")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        create_token(game, controller, _create_spirit_token())

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: AttacksTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(g):
                return False
            try:
                player_index = g.players.index(current_controller)
            except ValueError:
                return False
            if not g.cards_left_graveyards_this_turn.get(player_index):
                return False
            first_attacker = next(iter(g.combat_state.attackers), None)
            return event.attacker is first_attacker

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(g: GameState, _event: AttacksTriggeredEvent) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            candidates = [
                attacker
                for attacker in g.combat_state.attackers
                if getattr(attacker, "controller", None) is current_controller
            ]
            if not candidates:
                return None
            try:
                chosen = current_controller.choose_card(candidates, "Choose target attacking creature")
            except Exception:
                chosen = candidates[0]
            if chosen not in candidates:
                chosen = candidates[0]

            def _resolve(game_at_resolution: GameState, *, target: Creature = chosen) -> None:
                if (
                    getattr(target, "controller", None) is not current_controller
                    or target not in game_at_resolution.combat_state.attackers
                ):
                    return
                game_at_resolution.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.POWER_TOUGHNESS,
                        sublayer=SubLayer.MODIFY_PT,
                        apply=lambda _game, chosen_target=target: setattr(
                            chosen_target,
                            "modified_power",
                            chosen_target.modified_power + 2,
                        ),
                        duration=DURATION_END_OF_TURN,
                    )
                )
                game_at_resolution.effect_manager.apply_all(game_at_resolution)

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
