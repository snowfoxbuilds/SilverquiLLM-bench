"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfPrecombatMainTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard.

    Mirrors fdn_48 (Refute)'s local counter helper.
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
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
        targets = [
            so for so in game.stack.objects()
            if so.source is not self and getattr(so, "is_spell", True)
        ]
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
        target = _get_chosen_target(self)
        if target is None:
            return

        # Capture the mana spent to cast the targeted spell BEFORE countering.
        countered_card = getattr(target, "source", None)
        mana_spent = int(getattr(countered_card, "mana_spent", 0) or 0)

        _counter_spell(game, target)

        controller = self.controller
        if controller is None or mana_spent <= 0:
            return

        # Delayed: at the beginning of your next main phase, if you control a
        # Wizard, add {C} equal to the mana spent. One-shot. (The current
        # turn's precombat-main event has already fired, so the next firing is
        # genuinely "your next main phase".)
        from engine.triggers import TriggerRegistration

        marker = object()

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            has_wizard = any(
                CardType.CREATURE in getattr(c, "card_types", set())
                and "Wizard" in getattr(c, "subtypes", set())
                for c in game.get_battlefield(controller).get_all()
            )
            if has_wizard:
                controller.mana_pool.add(ManaType.COLORLESS, mana_spent)
            # One-shot: unregister this delayed trigger.
            game.trigger_manager.unregister(marker)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=marker,
                controller=controller,
            )
        )
