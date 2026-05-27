"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _is_spell_stack_object(obj: Any) -> bool:
    if not isinstance(obj, StackObject):
        return False
    return getattr(obj, "is_spell", False) is True


def _counter_spell(game: "GameState", stack_obj: StackObject) -> None:
    card = stack_obj.source

    stack_items = game.stack._items  # noqa: SLF001
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            break
    else:
        return

    for player in game.players:
        if player.zones[Zone.STACK].contains(card):
            move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
            break


def _controls_wizard(game: "GameState", player: Any) -> bool:
    if player is None:
        return False
    for permanent in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


def _schedule_next_main_phase_mana(
    game: "GameState",
    player: Any,
    amount: int,
) -> None:
    delayed_source = object()

    def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
        return event.player is player

    def _effect(game: "GameState") -> None:
        if player is not None and amount > 0:
            player.mana_pool.add(ManaType.COLORLESS, amount)
        game.trigger_manager.unregister(delayed_source)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=delayed_source,
            controller=player,
        )
    )


class ManaSculpt(Instant):
    """Mana Sculpt."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} "
            "equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        return any(_is_spell_stack_object(stack_obj) for stack_obj in game.stack.objects())

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=_is_spell_stack_object,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        target = _get_chosen_target(self)
        if not _is_spell_stack_object(target):
            return

        target_spell = target.source
        mana_spent = getattr(
            target_spell,
            "mana_spent_to_cast",
            0,
        )

        _counter_spell(game, target)

        controller = getattr(self, "controller", None)
        if _controls_wizard(game, controller):
            _schedule_next_main_phase_mana(game, controller, mana_spent)
