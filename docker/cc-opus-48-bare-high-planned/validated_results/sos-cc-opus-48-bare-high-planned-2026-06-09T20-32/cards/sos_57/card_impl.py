"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfPrecombatMainTriggeredEvent
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove it from the stack and bin the card."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return
    card = stack_obj.source
    stack_items = game.stack._items
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            break
    else:
        return
    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)
    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)
    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    if player is None:
        return False
    for obj in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C} equal
    to the amount of mana spent to cast that spell at the beginning of your
    next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        has_target = any(
            so.source is not self and getattr(so, "is_spell", True)
            for so in game.stack.objects()
        )
        if not has_target:
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
            return  # countered/illegal target — fizzle

        countered_card = getattr(target, "source", None)
        amount = int(getattr(countered_card, "mana_spent", 0) or 0)
        _counter_spell(game, target)

        controller = self.controller
        if controller is None or amount <= 0:
            return

        # Delayed refund: at the beginning of your next (precombat) main phase,
        # if you control a Wizard, add that much {C}.  One-shot.
        from engine.triggers import TriggerRegistration

        marker = object()

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            game.trigger_manager.unregister(marker)
            if _controls_wizard(game, controller):
                controller.mana_pool.add(ManaType.COLORLESS, amount)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=marker,
                controller=controller,
            )
        )
