"""Card implementation for Zealous Lorecaster."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ZealousLorecaster(Creature):
    """Zealous Lorecaster."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zealous Lorecaster")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}"))
        kwargs.setdefault("subtypes", {"Giant", "Sorcerer"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _create_etb_stack_object(g: GameState) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            graveyard = g.get_graveyard(current_controller)
            candidates = [
                card
                for card in graveyard.get_all()
                if bool(getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
            ]
            if not candidates:
                return None

            chosen = None
            preset_targets = getattr(source, "chosen_targets", [])
            if preset_targets:
                preset = preset_targets[0]
                if preset in candidates:
                    chosen = preset
            if chosen is None:
                try:
                    chosen = current_controller.choose_card(
                        candidates,
                        "Choose target instant or sorcery card in your graveyard",
                    )
                except Exception:
                    chosen = candidates[0]
            if chosen not in candidates:
                return None

            def _resolve(game_at_resolution: GameState, *, target=chosen, owner=current_controller) -> None:
                if not owner.zones[Zone.GRAVEYARD].contains(target):
                    return
                if not bool(getattr(target, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}):
                    return
                move_to_zone(game_at_resolution, target, Zone.GRAVEYARD, Zone.HAND)

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        if getattr(source, "_registering_after_enter_battlefield", False):
            stack_object = _create_etb_stack_object(game)
            if stack_object is not None:
                game.stack.push(stack_object)

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return (
                source.is_on_battlefield(g)
                and (event.permanent is source or event.creature is source or event.card is source)
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(
            g: GameState,
            _event: EntersBattlefieldTriggeredEvent,
        ) -> StackObject | None:
            return _create_etb_stack_object(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
