"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_MANA_COST = ManaCost(generic=1, pips={ManaType.BLUE: 2})


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard (mirrors fdn_48)."""
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


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

    SOS collector number 57.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", _MANA_COST)
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
            source = stack_obj.source
            if source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target spell on the stack."""
        targets = [
            so for so in game.stack.objects()
            if so.source is not self and getattr(so, "is_spell", True)
        ]
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    getattr(obj, "is_spell", True) and obj is not self
                ),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; possibly schedule mana for next main phase."""
        targets = getattr(self, "chosen_targets", [])
        target_so = targets[0] if targets else None

        if target_so is None:
            return

        # Count mana spent on the countered spell.
        countered_card = getattr(target_so, "source", None)
        mana_spent = 0
        if countered_card is not None:
            cost = getattr(countered_card, "mana_cost", None)
            if cost is not None:
                mana_spent = cost.cmc  # amount of mana spent = converted mana cost

        _counter_spell(game, target_so)

        controller = self.controller
        if controller is None:
            return

        # If you control a Wizard, schedule mana at beginning of your next main phase.
        if not _controls_wizard(game, controller):
            return

        if mana_spent <= 0:
            return

        _register_delayed_mana(game, controller, mana_spent)


def _controls_wizard(game: "GameState", controller: Any) -> bool:
    """Return True if controller has a Wizard on the battlefield."""
    for card in game.get_battlefield(controller).get_all():
        if "Wizard" in getattr(card, "subtypes", set()):
            return True
    return False


def _register_delayed_mana(game: "GameState", controller: Any, amount: int) -> None:
    """Register a one-shot trigger for the beginning of controller's next main phase."""
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.triggers import TriggerRegistration

    cast_turn = game.turn_number
    fired = [False]  # one-shot

    sentinel = object()  # unique source for unregistration

    def _condition(g: Any, event: Any) -> bool:
        # Fire for the active player's (main phase) — must be controller and must
        # be a turn AFTER the counterspell was cast.
        if fired[0]:
            return False
        if g.active_player is not controller:
            return False
        if g.turn_number <= cast_turn:
            return False
        return True

    def _effect(g: "GameState") -> None:
        if fired[0]:
            return
        fired[0] = True
        controller.mana_pool.add(ManaType.COLORLESS, amount)
        # Unregister ourselves
        g.trigger_manager.unregister(sentinel)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=sentinel,
            controller=controller,
        )
    )
