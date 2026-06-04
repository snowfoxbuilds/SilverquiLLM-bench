"""Card implementation for Mana Sculpt (SOS #57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source
    stack_items = game.stack._items
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break
    if not found:
        return

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)
    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)
    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)


def _controls_wizard(game: "GameState", player: "Player") -> bool:
    for obj in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


def _schedule_mana(game: "GameState", controller: "Player", amount: int) -> None:
    """Add *amount* {C} at the beginning of *controller*'s next main phase."""
    from engine.events import BeginningOfMainPhaseTriggeredEvent
    from engine.triggers import TriggerRegistration

    token = object()

    def _condition(game: Any, event: Any) -> bool:
        return getattr(event, "player", None) is controller

    def _effect(game: "GameState") -> None:
        controller.mana_pool.add(ManaType.COLORLESS, amount)
        game.trigger_manager.unregister(token)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=token,
            controller=controller,
        )
    )


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount "
            "of {C} equal to the amount of mana spent to cast that spell at "
            "the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        targets = [
            so
            for so in game.stack.objects()
            if so.source is not self and getattr(so, "is_spell", True)
        ]
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self
                and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        target = _get_chosen_target(self)
        if target is None:
            return
        countered_card = getattr(target, "source", None)
        mana_spent = int(getattr(countered_card, "mana_spent", 0) or 0)

        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return
        if mana_spent > 0 and _controls_wizard(game, controller):
            _schedule_mana(game, controller, mana_spent)
