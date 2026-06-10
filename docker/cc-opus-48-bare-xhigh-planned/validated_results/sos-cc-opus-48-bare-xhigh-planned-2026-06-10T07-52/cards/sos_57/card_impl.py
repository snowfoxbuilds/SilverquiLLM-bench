"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from the stack and bin its card to graveyard."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
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
    for c in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(c, "subtypes", set()):
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
        """Needs a spell (other than itself) on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        has_target = any(
            stack_obj.source is not self and getattr(stack_obj, "is_spell", True)
            for stack_obj in game.stack.objects()
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
        target = (getattr(self, "chosen_targets", []) or [None])[0]
        if target is None:
            return  # fizzles — target left the stack

        countered_card = getattr(target, "source", None)
        amount = getattr(countered_card, "mana_spent", None)
        if amount is None:
            cost = getattr(countered_card, "mana_cost", None)
            amount = cost.cmc if cost is not None else 0

        _counter_spell(game, target)

        controller = self.controller
        if controller is None or amount <= 0:
            return
        self._register_delayed_mana(game, controller, amount)

    def _register_delayed_mana(
        self, game: "GameState", controller: Any, amount: int
    ) -> None:
        """At the controller's next precombat main, if they control a Wizard,
        add ``amount`` {C}.  One-shot; unregisters after it fires."""
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        sentinel = object()
        stamp_turn = getattr(game, "turn_number", 0)

        def _condition(game: Any, event: Any) -> bool:
            # The controller's next precombat main (a later turn than the cast).
            return (
                game.active_player is controller
                and getattr(game, "turn_number", 0) > stamp_turn
            )

        def _effect(game: "GameState") -> None:
            if _controls_wizard(game, controller):
                controller.mana_pool.add(ManaType.COLORLESS, amount)
            game.trigger_manager.unregister(sentinel)  # one-shot

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=sentinel,
                controller=controller,
            )
        )
