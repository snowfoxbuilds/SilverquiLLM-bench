"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move its card to the graveyard."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    if not game.stack.remove(stack_obj):
        return

    card = stack_obj.source
    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)


def _controls_wizard(player: Any) -> bool:
    """Return True if *player* controls a creature with the Wizard subtype."""
    from engine.types import CardType

    for obj in player.zones[Zone.BATTLEFIELD].get_all():
        types = getattr(obj, "card_types", set())
        if CardType.CREATURE in types and "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


def _spell_mana_spent(card: Any) -> int:
    """Return the amount of mana spent to cast *card* (falls back to CMC)."""
    spent = getattr(card, "mana_spent", None)
    if spent is not None:
        return int(spent)
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


def _register_delayed_mana(game: "GameState", controller: Any, amount: int) -> None:
    """Register a one-shot trigger to add {C} at the controller's next main phase."""
    from engine.events import BeginningOfMainPhaseTriggeredEvent
    from engine.triggers import TriggerRegistration

    sentinel = object()  # unique source so we can unregister exactly this trigger

    def _condition(game: Any, event: Any) -> bool:
        return getattr(event, "player", None) is controller

    def _effect(game: "GameState") -> None:
        controller.mana_pool.add(ManaType.COLORLESS, amount)
        game.trigger_manager.unregister(sentinel)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=sentinel,
            controller=controller,
        )
    )


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell.  If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
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
        self.colors = ["U"]

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a spell on the stack."""
        targets = [
            stack_obj
            for stack_obj in game.stack.objects()
            if stack_obj.source is not self and getattr(stack_obj, "is_spell", True)
        ]
        if not targets:
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
        """Counter the target spell and, with a Wizard, set up delayed mana."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        mana_spent = _spell_mana_spent(getattr(target, "source", None))
        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return
        if _controls_wizard(controller) and mana_spent > 0:
            _register_delayed_mana(game, controller, mana_spent)
