"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> bool:
    """Counter a spell — remove from stack and move card to graveyard.

    Returns True if the spell was actually countered, False if it was not
    on the stack (e.g., already left stack before resolution).
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return False

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return False

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        try:
            stack_zone = controller.zones[Zone.STACK]
            if stack_zone.contains(card):
                stack_zone.remove(card)
        except (KeyError, AttributeError):
            pass

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)

    return True


def _controller_has_wizard(game: "GameState", controller: Any) -> bool:
    """Return True if controller controls a Wizard on the battlefield."""
    from engine.types import Zone

    if controller is None:
        return False

    try:
        battlefield = controller.zones[Zone.BATTLEFIELD]
        for permanent in battlefield.get_all():
            subtypes = getattr(permanent, "subtypes", set())
            if "Wizard" in subtypes:
                return True
    except (KeyError, AttributeError):
        pass
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
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
        """Cannot cast unless there's a spell on the stack to counter."""
        from engine.stack import StackObject

        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "source") and hasattr(obj, "controller")
                ),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell, and if a Wizard is controlled, schedule mana reward."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_stack_obj = chosen[0]
        target_card = getattr(target_stack_obj, "source", None)

        # Determine mana value of the countered spell.
        # Prefer the actual amount of mana spent to cast it (if stored),
        # falling back to the card's converted mana cost.
        mana_value = 0
        if target_card is not None:
            # Check for actual mana spent (set by the casting engine if available)
            mana_paid = getattr(target_stack_obj, "mana_paid", None)
            if mana_paid is not None:
                mana_value = int(mana_paid)
            else:
                mc = getattr(target_card, "mana_cost", None)
                if mc is not None:
                    mana_value = mc.cmc

        # Counter the spell; only proceed with trigger if it was actually countered
        actually_countered = _counter_spell(game, target_stack_obj)

        if not actually_countered:
            return

        # If controller has a Wizard, register delayed trigger for next main phase
        controller = self.controller
        if not _controller_has_wizard(game, controller):
            return

        # Create a one-shot delayed trigger for the beginning of controller's next main phase
        source_marker = object()  # unique marker for this trigger
        mana_amount = mana_value

        def _condition(g: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return event.player is controller

        def _effect(g: "GameState") -> None:
            # Add colorless mana
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, mana_amount)
            # Unregister self (one-shot)
            g.trigger_manager.unregister(source_marker)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source_marker,
                controller=controller,
            )
        )
