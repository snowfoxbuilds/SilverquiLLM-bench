"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to owner's graveyard."""
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
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Requires a spell on the stack to target."""
        from engine.stack import StackObject

        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "source")  # StackObject
                    and obj.source is not self
                    and getattr(obj, "is_spell", True)
                ),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; if you control a Wizard add mana next main phase."""
        controller = self.controller
        if controller is None:
            return

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Determine the CMC of the countered spell (for mana refund)
        countered_card = getattr(target, "source", None)
        countered_cmc = 0
        if countered_card is not None:
            mana_cost = getattr(countered_card, "mana_cost", None)
            if mana_cost is not None:
                countered_cmc = mana_cost.cmc

        _counter_spell(game, target)

        # Check if controller controls a Wizard
        controls_wizard = False
        bf = game.get_battlefield(controller)
        for obj in bf.get_all():
            if "Wizard" in getattr(obj, "subtypes", set()):
                controls_wizard = True
                break

        if controls_wizard and countered_cmc > 0:
            # Register a one-shot trigger for the beginning of the next main phase.
            source = self
            mana_amount = countered_cmc
            fired = [False]

            from engine.triggers import TriggerRegistration
            from engine.events import BeginningOfMainPhaseTriggeredEvent
            from engine.types import ManaType

            def _main_condition(g: Any, event: Any) -> bool:
                return (
                    not fired[0]
                    and getattr(event, "player", None) is controller
                )

            def _main_effect(g: Any) -> None:
                if fired[0]:
                    return
                fired[0] = True
                controller.mana_pool.add(ManaType.COLORLESS, mana_amount)
                # Unregister this one-shot trigger
                g.trigger_manager.unregister(source)

            game.trigger_manager.register(TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_main_condition,
                effect=_main_effect,
                source=source,
                controller=controller,
            ))


