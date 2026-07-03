"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
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
            "of {C} equal to the amount of mana spent to cast that spell at "
            "the beginning of your next main phase.",
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
        """Target a spell on the stack."""
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
        """Counter target spell; if you control a Wizard, delay-add mana."""
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        target = _get_chosen_target(self, game)
        if target is None:
            return

        mana_spent = getattr(target, "mana_spent_total", 0)
        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        # Check for a Wizard the controller controls.
        bf = game.get_battlefield(controller)
        has_wizard = any(
            "Wizard" in getattr(c, "subtypes", set())
            and CardType.CREATURE in getattr(c, "card_types", set())
            for c in bf.get_all()
        )

        if not has_wizard or mana_spent <= 0:
            return

        # Register a one-shot trigger: at the beginning of controller's next
        # main phase, add mana_spent {C}.
        _reg_holder: list[Any] = [None]

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _delayed_effect(g: Any) -> None:
            controller.mana_pool.add(ManaType.COLORLESS, mana_spent)
            # One-shot: remove this trigger after it fires.
            t = _reg_holder[0]
            if t is not None:
                g.trigger_manager._triggers = [  # noqa: SLF001
                    x for x in g.trigger_manager._triggers if x is not t
                ]

        reg = TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_delayed_effect,
            source=self,
            controller=controller,
        )
        _reg_holder[0] = reg
        game.trigger_manager.register(reg)
