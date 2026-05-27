"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Return the first chosen target for this spell, if any."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> bool:
    """Counter a spell by removing it from the stack and putting it into its owner's graveyard."""
    if not isinstance(stack_obj, StackObject):
        return False

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
    for index, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(index)
            break
    else:
        return False

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)
    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)
    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)
    return True


def _controls_wizard(controller: Any) -> bool:
    """Return True if controller currently controls a Wizard permanent."""
    if controller is None:
        return False
    for permanent in controller.zones[Zone.BATTLEFIELD].get_all():
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


def _mana_spent_to_cast(stack_obj: Any) -> int:
    """Return the stable public amount of mana actually spent to cast a spell."""
    if stack_obj is None:
        return 0
    if hasattr(stack_obj, "mana_spent_to_cast"):
        return int(getattr(stack_obj, "mana_spent_to_cast", 0))
    source = getattr(stack_obj, "source", None)
    if source is not None and hasattr(source, "mana_spent_to_cast"):
        return int(getattr(source, "mana_spent_to_cast", 0))
    mana_cost = getattr(source, "mana_cost", None)
    return int(getattr(mana_cost, "cmc", 0))


class ManaSculpt(Instant):
    """Mana Sculpt — counter target spell, then maybe delay colorless mana."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} "
            "equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Mana Sculpt requires another spell to already be on the stack."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target a single spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell and, if you control a Wizard, delay colorless mana."""
        target = _get_chosen_target(self, game)
        if target is None or not getattr(target, "is_spell", True):
            return

        mana_spent = _mana_spent_to_cast(target)
        was_countered = _counter_spell(game, target)
        if not was_countered:
            return

        controller = self.controller
        if not _controls_wizard(controller) or controller is None or mana_spent <= 0:
            return

        delayed_source = object()

        def _condition(trigger_game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return trigger_game.active_player is controller

        def _effect(trigger_game: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, mana_spent)
            trigger_game.trigger_manager.unregister(delayed_source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=delayed_source,
                controller=controller,
            )
        )
