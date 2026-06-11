"""Card implementation for Essenceknit Scholar."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    AttacksTriggeredEvent,
    EndStepTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
    GainsLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import create_token, draw_card
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class _PestToken(Creature):
    """1/1 black and green Pest token with an attack-triggered life gain ability."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest")
        kwargs.setdefault("subtypes", {"Pest"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)
        self.colors = {Color.BLACK, Color.GREEN}  # type: ignore[attr-defined]
        self.snapshot_current_characteristics()

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_game: GameState, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(
            _game: GameState,
            _event: AttacksTriggeredEvent,
        ) -> StackObject | None:
            locked_controller = getattr(source, "controller", None)
            if locked_controller is None:
                return None

            def _resolve(g: GameState, *, player=locked_controller) -> None:
                player.life += 1
                player.life_gained_this_turn = getattr(player, "life_gained_this_turn", 0) + 1
                g.trigger_manager.fire_event(
                    g,
                    GainsLifeTriggeredEvent(player=player, amount=1),
                )

            return StackObject(
                source=source,
                controller=locked_controller,
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


class EssenceknitScholar(Creature):
    """Essenceknit Scholar."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Essenceknit Scholar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B/G}{G}"))
        kwargs.setdefault("subtypes", {"Dryad", "Warlock"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _etb_condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return (
                source.is_on_battlefield(g)
                and (event.permanent is source or event.creature is source or event.card is source)
            )

        def _etb_effect(g: GameState) -> None:
            return

        def _create_etb_stack_object(g: GameState) -> StackObject | None:
            locked_controller = getattr(source, "controller", None)
            if locked_controller is None:
                return None

            def _resolve(game_at_resolution: GameState, *, player=locked_controller) -> None:
                create_token(game_at_resolution, player, _PestToken())

            return StackObject(
                source=source,
                controller=locked_controller,
                on_resolve=_resolve,
            )

        def _end_step_condition(g: GameState, event: EndStepTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
                and any(
                    getattr(creature, "controller", None) is current_controller
                    for creature in getattr(g, "creatures_died_this_turn", [])
                )
            )

        def _end_step_effect(g: GameState) -> None:
            return

        def _create_end_step_stack_object(
            _g: GameState,
            event: EndStepTriggeredEvent,
        ) -> StackObject | None:
            locked_controller = getattr(event, "player", None)
            if locked_controller is None:
                return None

            def _resolve(game_at_resolution: GameState, *, player=locked_controller) -> None:
                draw_card(game_at_resolution, player)

            return StackObject(
                source=source,
                controller=locked_controller,
                on_resolve=_resolve,
            )

        if getattr(source, "_registering_after_enter_battlefield", False):
            stack_object = _create_etb_stack_object(game)
            if stack_object is not None:
                game.stack.push(stack_object)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_etb_condition,
                effect=_etb_effect,
                source=self,
                controller=controller,
                create_stack_object=lambda g, _event: _create_etb_stack_object(g),
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_end_step_condition,
                effect=_end_step_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_end_step_stack_object,
            )
        )
