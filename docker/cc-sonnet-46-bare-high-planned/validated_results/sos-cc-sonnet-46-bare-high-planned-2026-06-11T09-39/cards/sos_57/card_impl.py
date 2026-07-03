"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: Any, stack_obj: Any) -> None:
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


def _controls_wizard(game: Any, player: Any) -> bool:
    """Return True if player controls at least one Wizard on the battlefield."""
    bf = game.get_battlefield(player)
    for perm in bf.get_all():
        if "Wizard" in getattr(perm, "subtypes", set()):
            return True
    return False


def _register_delayed_mana(game: Any, controller: Any, mana_amount: int) -> None:
    """Register a one-shot trigger: at your next precombat main phase, add {C} * mana_amount.

    Deliberate limitation: fires only at precombat main (BeginningOfPrecombatMainTriggeredEvent),
    not postcombat main, because E2 covers only the precombat phase.
    """
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.triggers import TriggerRegistration

    sentinel: object = object()  # unique per registration so unregister is precise

    def _condition(game: Any, event: Any) -> bool:
        return game.active_player is controller

    def _effect(game: Any) -> None:
        controller.mana_pool.add(ManaType.COLORLESS, mana_amount)
        game.trigger_manager.unregister(sentinel)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=sentinel,
            controller=controller,
        )
    )


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
        """Only castable when there is a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; if controller has a Wizard, schedule delayed mana."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]

        # Record mana value before countering (proxy for "mana spent").
        source_card = target.source
        cost = getattr(source_card, "mana_cost", None)
        mana_spent = cost.cmc if cost is not None else 0

        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        if mana_spent > 0 and _controls_wizard(game, controller):
            _register_delayed_mana(game, controller, mana_spent)
