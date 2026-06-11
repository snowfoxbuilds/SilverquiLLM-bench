"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return True if *player* controls at least one Wizard on the battlefield."""
    bf = game.get_battlefield(player)
    for perm in bf.get_all():
        if "Wizard" in getattr(perm, "subtypes", set()):
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
        """Cannot cast unless there's a spell on the stack to counter."""
        from engine.stack import StackObject

        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target spell on the stack."""
        from engine.stack import StackObject

        targets = []
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; maybe add mana next main phase."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Measure mana spent before countering (card's CMC = mana spent proxy).
        # KEY_DECISION: using CMC as mana-spent since actual-spend tracking would
        # require engine changes; CMC is equal to actual spend for non-X spells.
        countered_card = getattr(target, "source", None)
        mana_spent = 0
        if countered_card is not None:
            mana_cost = getattr(countered_card, "mana_cost", None)
            if mana_cost is not None:
                mana_spent = mana_cost.cmc

        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        if mana_spent <= 0 or not _controls_wizard(game, controller):
            return

        # Register a one-shot trigger for the caster's next precombat main phase.
        _register_delayed_mana_trigger(game, controller, mana_spent)


def _register_delayed_mana_trigger(
    game: "GameState", controller: Any, mana_amount: int
) -> None:
    """Register a one-shot trigger that adds {C} at the controller's next main phase."""
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.triggers import TriggerRegistration

    fired = [False]

    def _condition(game: Any, event: Any) -> bool:
        if fired[0]:
            return False
        return game.active_player is controller

    def _effect(game: "GameState") -> None:
        if fired[0]:
            return
        fired[0] = True
        controller.mana_pool.add(ManaType.COLORLESS, mana_amount)
        # Unregister — the trigger source is the closure itself, so we
        # remove by the unique closure object.  Since TriggerRegistration
        # tracks source by identity, we use a sentinel object for removal.
        game.trigger_manager.unregister(_sentinel)

    _sentinel = object()
    reg = TriggerRegistration(
        event_type=BeginningOfPrecombatMainTriggeredEvent,
        condition=_condition,
        effect=_effect,
        source=_sentinel,
        controller=controller,
    )
    game.trigger_manager.register(reg)
