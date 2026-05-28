"""Card implementation for Mana Sculpt.

Mana Sculpt — {1}{U}{U} — Instant (Rare)
Counter target spell. If you control a Wizard, add an amount of {C}
equal to the amount of mana spent to cast that spell at the beginning
of your next main phase.

Xmage analog: Mana Drain (counter + delayed-trigger refund) + Arcane
Epiphany (Wizard-conditional).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost(generic=1, pips={ManaType.BLUE: 2}))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return spells on the stack as legal targets (not abilities)."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            # Only target spells (cards being cast), not activated/triggered abilities.
            # Spells have a source card with card_types defined.
            source = getattr(stack_obj, "source", None)
            if source is not None and hasattr(source, "card_types"):
                targets.append(stack_obj)
        return targets

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell. Wizard-conditional delayed mana refund."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_stack_obj = chosen[0]

        # Fizzle check: if the target is no longer on the stack, do nothing.
        stack_items = game.stack._items
        if target_stack_obj not in stack_items:
            return

        # Record mana_spent BEFORE removing the stack object (the engine sets
        # this at cast time on the StackObject; see engine/casting.py).
        mana_spent = getattr(target_stack_obj, "mana_spent", 0)

        # Remove target from the stack (counter it)
        stack_items.remove(target_stack_obj)

        # Move the spell card to owner's graveyard (countering)
        source_card = getattr(target_stack_obj, "source", None)
        if source_card is not None:
            owner = getattr(source_card, "owner", None)
            controller = getattr(source_card, "controller", owner)
            # Remove from stack zone if present
            if owner is not None and hasattr(owner, "zones"):
                stack_zone = owner.zones[Zone.STACK]
                if stack_zone.contains(source_card):
                    stack_zone.remove(source_card)
            elif controller is not None and hasattr(controller, "zones"):
                stack_zone = controller.zones[Zone.STACK]
                if stack_zone.contains(source_card):
                    stack_zone.remove(source_card)
            # Move to owner's graveyard
            if owner is not None and hasattr(owner, "zones"):
                gy = owner.zones[Zone.GRAVEYARD]
                gy.add(source_card)

        # Wizard-conditional delayed refund: if controller controls a Wizard
        # at resolution time, register a one-shot trigger that adds {C} ×
        # mana_spent at the beginning of controller's next main phase.
        my_controller = getattr(self, "controller", None)
        if my_controller is None or mana_spent <= 0:
            return

        battlefield = my_controller.zones[Zone.BATTLEFIELD]
        if battlefield is None:
            return
        has_wizard = any(
            "Wizard" in getattr(perm, "subtypes", set())
            for perm in battlefield.get_all()
        )
        if not has_wizard:
            return

        _register_delayed_refund(game, my_controller, mana_spent)


def _register_delayed_refund(
    game: "GameState",
    refund_controller: Any,
    amount: int,
) -> None:
    """Register a one-shot trigger that fires at the controller's next main phase.

    On the first ``BeginningOfMainPhaseEvent`` where ``event.player`` matches
    the refund controller, add ``amount`` colorless mana to their pool and
    unregister the trigger (so it doesn't fire on subsequent main phases).
    """
    # Use a unique sentinel object as the trigger's "source" so unregistration
    # by identity removes exactly this trigger and nothing else.
    sentinel: object = object()
    fired = [False]

    def _condition(g: "GameState", event: BeginningOfMainPhaseEvent) -> bool:
        if fired[0]:
            return False
        return getattr(event, "player", None) is refund_controller

    def _effect(g: "GameState") -> None:
        if fired[0]:
            return
        fired[0] = True
        refund_controller.mana_pool.add(ManaType.COLORLESS, amount)
        g.trigger_manager.unregister(sentinel)

    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfMainPhaseEvent,
        condition=_condition,
        effect=_effect,
        source=sentinel,
        controller=refund_controller,
    ))
