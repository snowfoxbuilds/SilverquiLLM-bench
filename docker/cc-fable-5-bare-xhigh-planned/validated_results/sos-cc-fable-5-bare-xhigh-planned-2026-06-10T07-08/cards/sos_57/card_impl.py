"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell (mirrors fdn_48)."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard."""
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
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    return any(
        "Wizard" in getattr(obj, "subtypes", set())
        for obj in game.get_battlefield(player).get_all()
    )


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

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target spell on the stack (mirrors fdn_48 Refute)."""
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

    def on_resolve(self, game: "GameState") -> None:
        """Counter the spell; set up the delayed mana for your next main phase."""
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration
        from engine.types import ManaType

        target = _get_chosen_target(self, game)
        if target is None:
            return  # fizzle

        # Amount actually paid to cast the countered spell, recorded by the
        # casting pipeline at payment time (0 for free-cast spells).
        amount = getattr(getattr(target, "source", None), "mana_spent", 0) or 0

        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        # Delayed one-shot: at the beginning of your next (precombat) main
        # phase, if you control a Wizard, add {C} × amount.
        marker = object()

        def _condition(g: Any, event: Any) -> bool:
            if g.active_player is not controller:
                return False
            # One-shot: consume the registration as soon as it fires.
            g.trigger_manager.unregister(marker)
            return True

        def _effect(g: "GameState") -> None:
            if amount > 0 and _controls_wizard(g, controller):
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
