"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove it from the stack and move its card to the
    graveyard.  (Mirrors the FDN counterspell helper, fdn_48.)"""
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
    return any(
        "Wizard" in getattr(c, "subtypes", set())
        for c in game.get_battlefield(player).get_all()
    )


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell.  If you control a Wizard, add an amount of {C} equal
    to the amount of mana spent to cast that spell at the beginning of your next
    main phase.

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
        """Needs a spell on the stack to counter."""
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
        target = None
        chosen = getattr(self, "chosen_targets", None)
        if chosen:
            target = chosen[0]
        if target is None:
            return  # fizzles — no legal target

        amount = getattr(getattr(target, "source", None), "mana_spent", 0)
        _counter_spell(game, target)

        controller = self.controller
        if controller is None or amount <= 0:
            return

        self._schedule_delayed_mana(game, controller, amount)

    def _schedule_delayed_mana(self, game: "GameState", controller: Any, amount: int) -> None:
        """At the beginning of your next main phase, if you control a Wizard,
        add ``amount`` {C}.  One-shot."""
        from engine.triggers import TriggerRegistration
        from engine.events import BeginningOfPrecombatMainTriggeredEvent

        marker = object()  # unique source so this trigger unregisters cleanly
        cast_turn = game.turn_number

        def _condition(g: "GameState", event: Any) -> bool:
            return g.active_player is controller and g.turn_number > cast_turn

        def _effect(g: "GameState") -> None:
            # "If you control a Wizard" — evaluated when the delayed ability fires.
            if _controls_wizard(g, controller):
                controller.mana_pool.add(ManaType.COLORLESS, amount)
            g.trigger_manager.unregister(marker)  # one-shot

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=marker,
                controller=controller,
            )
        )
