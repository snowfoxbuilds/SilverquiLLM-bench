"""Card implementation for Pestbrood Sloth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    AttacksTriggeredEvent,
    CreatureDiesTriggeredEvent,
    GainsLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class _PestToken(Creature):
    """1/1 black and green Pest token with an attack trigger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest")
        kwargs.setdefault("subtypes", {"Pest"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)
        self.colors = {Color.BLACK, Color.GREEN}
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


class PestbroodSloth(Creature):
    """Pestbrood Sloth."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pestbrood Sloth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("subtypes", {"Plant", "Sloth"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(_game: GameState, event: CreatureDiesTriggeredEvent) -> bool:
            return event.creature is source

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(
            _game: GameState,
            event: CreatureDiesTriggeredEvent,
        ) -> StackObject | None:
            token_controller = event.controller or getattr(source, "controller", None)
            if token_controller is None:
                return None

            def _resolve(g: GameState, *, player=token_controller) -> None:
                create_token(g, player, _PestToken())
                create_token(g, player, _PestToken())

            return StackObject(
                source=source,
                controller=token_controller,
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CreatureDiesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
