"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: GameState, stack_obj: Any) -> bool:
    """Counter a spell — remove from stack, move card to graveyard.

    Returns ``True`` if the spell was found on the stack and countered.
    Mirrors fdn_48 (Refute).
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
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)
    return True


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
            "of {C} equal to the amount of mana spent to cast that spell "
            "at the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast unless there's a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target spell on the stack."""
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
                filter_fn=lambda obj: getattr(obj, "source", None) is not self
                and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        target = _get_chosen_target(self)
        if target is None:
            return

        # The amount of mana actually spent on the spell, recorded at
        # payment time by cast_spell (0 for free casts).
        amount = getattr(getattr(target, "source", None), "mana_spent", 0) or 0

        if not _counter_spell(game, target):
            return  # target already left the stack — spell does nothing

        controller = self.controller
        if controller is None or amount <= 0:
            return

        # Delayed one-shot: at the beginning of your next main phase, if
        # you control a Wizard, add that much {C}.
        marker = object()

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: GameState) -> None:
            g.trigger_manager.unregister(marker)
            controls_wizard = any(
                "Wizard" in getattr(perm, "subtypes", set())
                for perm in g.get_battlefield(controller).get_all()
            )
            if controls_wizard:
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
