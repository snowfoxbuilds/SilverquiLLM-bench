"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell by removing it from the stack and moving to graveyard."""
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


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C} equal
    to the amount of mana spent to cast that spell at the beginning of your
    next main phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} "
            "equal to the amount of mana spent to cast that spell at the beginning "
            "of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Can only cast if there is a spell on the stack to counter."""
        from engine.stack import StackObject
        for obj in game.stack.objects():
            if obj.source is self:
                continue
            if getattr(obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "source") and obj.source is not self and
                    getattr(obj, "is_spell", True)
                ),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        target_so = targets[0] if targets else None
        if target_so is None:
            return

        # Record mana spent on the countered spell before countering.
        # The mana cost is the spell's mana cost's total (mana value).
        target_card = getattr(target_so, "source", None)
        if target_card is None:
            return

        # "mana spent to cast" = sum of pip counts + generic + X.
        mana_value = 0
        if target_card.mana_cost is not None:
            mc = target_card.mana_cost
            mana_value = mc.generic + sum(mc.pips.values()) + sum(
                1 for _ in (mc.hybrid or [])
            )

        _counter_spell(game, target_so)

        controller = self.controller
        if controller is None:
            return

        # Check if controller has a Wizard.
        if not self._controls_wizard(game, controller):
            return

        # Register a one-shot trigger on next BeginningOfPrecombatMainTriggeredEvent.
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        # Stamp the current turn so we fire on the NEXT main phase.
        cast_turn = game.turn_number
        trigger_holder = [None]  # so we can unregister after firing

        def _condition(g: Any, event: Any) -> bool:
            active = g.active_player
            return active is controller and g.turn_number > cast_turn

        def _effect(g: "GameState") -> None:
            ctrl = controller
            ctrl.mana_pool.add(ManaType.COLORLESS, mana_value)
            # Unregister after firing (one-shot).
            if trigger_holder[0] is not None:
                g.trigger_manager.unregister(trigger_holder[0])

        # Use a unique sentinel as the source so we can unregister it.
        sentinel = object()
        trigger_holder[0] = sentinel

        # We need the controller for the trigger registration.
        reg = TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=sentinel,
            controller=controller,
        )
        game.trigger_manager.register(reg)

    def _controls_wizard(self, game: "GameState", controller: Any) -> bool:
        """Return True if controller controls at least one Wizard."""
        bf = game.get_battlefield(controller)
        for obj in bf.get_all():
            if "Wizard" in getattr(obj, "subtypes", set()):
                return True
        return False
