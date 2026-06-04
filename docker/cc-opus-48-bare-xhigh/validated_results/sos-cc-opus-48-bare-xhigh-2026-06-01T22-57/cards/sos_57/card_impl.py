"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
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


def _controls_wizard(player: Any) -> bool:
    """Return ``True`` if *player* controls a creature with the Wizard subtype."""
    if player is None:
        return False
    bf = player.zones[Zone.BATTLEFIELD]
    for obj in bf.get_all():
        if CardType.CREATURE not in getattr(obj, "card_types", set()):
            continue
        if "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


def _spell_mana_value(stack_obj: Any) -> int:
    """Return the amount of mana spent to cast the spell on *stack_obj*.

    Prefers the actual mana paid (``mana_spent``, recorded by the casting
    pipeline); falls back to the spell's mana value if that is unavailable.
    """
    source = getattr(stack_obj, "source", None)
    amount = getattr(source, "mana_spent", None)
    if amount is not None:
        return int(amount)
    cost = getattr(source, "mana_cost", None)
    if cost is not None:
        return cost.cmc
    return 0


class _DelayedManaSource:
    """Lightweight identity object owning the delayed-mana trigger."""

    name = "Mana Sculpt (delayed mana)"


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
                filter_fn=lambda obj: obj is not self
                and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell; schedule delayed colorless mana."""
        target = _get_chosen_target(self)
        if target is None:
            return

        amount = _spell_mana_value(target)
        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return
        if not _controls_wizard(controller):
            return
        if amount <= 0:
            return

        self._schedule_delayed_mana(game, controller, amount)

    @staticmethod
    def _schedule_delayed_mana(
        game: "GameState", controller: Any, amount: int
    ) -> None:
        """Register a one-shot trigger that adds {C} at the next main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = _DelayedManaSource()

        def _condition(game: "GameState", event: Any) -> bool:
            return getattr(event, "player", None) is controller

        def _effect(game: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            game.trigger_manager.unregister(source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
