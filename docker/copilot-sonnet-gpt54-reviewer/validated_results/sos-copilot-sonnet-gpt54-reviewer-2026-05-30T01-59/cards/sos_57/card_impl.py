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
    """Return True if player controls at least one Wizard creature."""
    bf = game.get_battlefield(player)
    for perm in bf.get_all():
        if "Wizard" in getattr(perm, "subtypes", set()):
            return True
    return False


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
        """Return target requirement for a spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; if controller has a Wizard, schedule mana refund."""
        target = _get_chosen_target(self)
        if target is None:
            return

        # Get CMC of the target spell before countering it
        source_card = getattr(target, "source", None)
        cmc = 0
        if source_card is not None:
            cost = getattr(source_card, "mana_cost", None)
            if cost is not None:
                cmc = cost.cmc

        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        # Only schedule mana refund if controller controls a Wizard
        if not _controls_wizard(game, controller) or cmc == 0:
            return

        # Register a one-shot delayed trigger for beginning of next main phase
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        # Sentinel uniquely identifies this trigger registration
        sentinel = object()
        fired = [False]

        def _condition(g: "GameState", event: Any) -> bool:
            return g.active_player is controller and not fired[0]

        def _effect(g: "GameState") -> None:
            if fired[0]:
                return
            fired[0] = True
            for _ in range(cmc):
                controller.mana_pool.add(ManaType.COLORLESS, 1)
            g.trigger_manager.unregister(sentinel)

        reg = TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=sentinel,
            controller=controller,
        )
        game.trigger_manager.register(reg)
