"""Card implementation for Practiced Scrollsmith."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Land
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_noncreature_nonland(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    return CardType.CREATURE not in card_types and CardType.LAND not in card_types and not isinstance(card, Land)


class PracticedScrollsmith(Creature):
    """Practiced Scrollsmith."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Practiced Scrollsmith")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{R/W}{W}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _target_requirement(current_controller: Any) -> TargetRequirement:
            graveyard = game.get_graveyard(current_controller)
            return TargetRequirement(
                filter_fn=lambda card, current_graveyard=graveyard: _is_noncreature_nonland(card)
                and current_graveyard.contains(card),
                description="target noncreature, nonland card from your graveyard",
                zone=Zone.GRAVEYARD,
            )

        def _condition(g: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and getattr(event, "permanent", None) is source
                and source.is_on_battlefield(g)
                and any(_is_noncreature_nonland(card) for card in g.get_graveyard(current_controller).get_all())
            )

        def _effect(_g: GameState) -> None:
            return

        def _create_stack_object(g: GameState, event: EntersBattlefieldTriggeredEvent) -> StackObject | None:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            requirement = _target_requirement(current_controller)
            graveyard = g.get_graveyard(current_controller)
            eligible = [card for card in graveyard.get_all() if requirement.filter_fn(card)]
            if not eligible:
                return None
            try:
                chosen = current_controller.choose_target([requirement], requirement)
            except Exception:
                chosen = eligible[0]
            if chosen not in eligible:
                chosen = eligible[0]

            def _resolve(game_at_resolution: GameState, *, target: Any = chosen) -> None:
                controller_at_resolution = getattr(source, "controller", None)
                if controller_at_resolution is None:
                    return
                controller_graveyard = game_at_resolution.get_graveyard(controller_at_resolution)
                if not controller_graveyard.contains(target):
                    return
                if not _is_noncreature_nonland(target):
                    return
                move_to_zone(game_at_resolution, target, Zone.GRAVEYARD, Zone.EXILE)
                game_at_resolution.grant_exile_play_permission_until_end_of_next_turn(
                    controller_at_resolution,
                    target,
                    source=source,
                )

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

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
