"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    """Return the chosen stack object, if any."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> Any | None:
    """Counter a spell on the stack and return its source card."""
    from engine.stack import StackObject
    from engine.zones import move_to_zone

    if not isinstance(stack_obj, StackObject):
        return None

    stack_items = game.stack._items  # noqa: SLF001
    for index, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(index)
            source = stack_obj.source
            move_to_zone(game, source, Zone.STACK, Zone.GRAVEYARD)
            return source
    return None


class ManaSculpt(Instant):
    """Mana Sculpt."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} "
            "equal to the amount of mana spent to cast that spell at the beginning "
            "of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Mana Sculpt needs another spell on the stack."""
        for stack_obj in game.stack.objects():
            if getattr(stack_obj, "source", None) is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a spell on the stack."""
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    getattr(getattr(obj, "source", obj), "object_id", None) != self.object_id
                    and getattr(obj, "is_spell", True)
                ),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell and schedule the Wizard rider if needed."""
        controller = self.controller
        target = _get_chosen_target(self)
        if controller is None or target is None:
            return

        target_card = getattr(target, "source", None)
        mana_spent = int(getattr(target_card, "actual_mana_spent", 0))
        countered = _counter_spell(game, target)
        if countered is None:
            return

        battlefield = game.get_battlefield(controller)
        controls_wizard = any(
            "Wizard" in getattr(permanent, "subtypes", set())
            for permanent in battlefield.get_all()
        )
        if not controls_wizard or mana_spent <= 0:
            return

        def _add_colorless(g: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, mana_spent)

        game.schedule_for_next_main_phase(controller, _add_colorless)
