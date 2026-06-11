"""Card implementation for Moseo, Vein's New Dean."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import (
    AttacksTriggeredEvent,
    EndStepTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
    GainsLifeTriggeredEvent,
)
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, Supertype, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class _PestToken(Creature):
    """1/1 black and green Pest token that gains its controller 1 life on attack."""

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

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            current_controller.life += 1
            current_controller.life_gained_this_turn = (
                getattr(current_controller, "life_gained_this_turn", 0) + 1
            )
            g.trigger_manager.fire_event(
                g,
                GainsLifeTriggeredEvent(player=current_controller, amount=1),
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


class MoseoVeinsNewDean(Creature):
    """Moseo, Vein's New Dean."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Moseo, Vein's New Dean")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Bird", "Skeleton", "Warlock"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen Moseo enters, create a 1/1 black and green Pest creature token with "
            '"Whenever this token attacks, you gain 1 life."\nInfusion — At the beginning of '
            "your end step, if you gained life this turn, return up to one target creature card "
            "with mana value X or less from your graveyard to the battlefield, where X is the "
            "amount of life you gained this turn.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _etb_condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and g.get_battlefield(current_controller).contains(source)
                and event.permanent is source
            )

        def _etb_effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            create_token(g, current_controller, _PestToken())

        def _end_step_condition(g: GameState, event: EndStepTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and g.get_battlefield(current_controller).contains(source)
                and getattr(current_controller, "life_gained_this_turn", 0) > 0
            )

        def _end_step_effect(_g: GameState) -> None:
            return

        def _create_end_step_stack_object(
            g: GameState,
            event: EndStepTriggeredEvent,  # noqa: ARG001
        ) -> StackObject:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return StackObject(source=source, controller=controller, on_resolve=lambda _g: None)

            max_mana_value = getattr(current_controller, "life_gained_this_turn", 0)
            graveyard = g.get_graveyard(current_controller)
            candidates = [
                card
                for card in graveyard.get_all()
                if isinstance(card, Creature) and getattr(card, "mana_cost", None).cmc <= max_mana_value
            ]

            chosen = None
            if candidates:
                try:
                    chosen = current_controller.choose_card(
                        candidates,
                        "creature card to return to the battlefield",
                    )
                except Exception:
                    chosen = candidates[0]
                if chosen not in candidates:
                    chosen = candidates[0]

            def _resolve(resolution_game: GameState, *, target: Creature | None = chosen) -> None:
                controller_at_resolution = getattr(source, "controller", None)
                if controller_at_resolution is None or target is None:
                    return
                controller_graveyard = resolution_game.get_graveyard(controller_at_resolution)
                if not controller_graveyard.contains(target):
                    return
                target.controller = controller_at_resolution
                move_to_zone(resolution_game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[] if chosen is None else [chosen],
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_etb_condition,
                effect=_etb_effect,
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
                create_stack_object=_create_end_step_stack_object,
            )
        )
