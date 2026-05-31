"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.triggers import register_delayed_next_main_phase_trigger
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> Any | None:
    """Counter a spell and return its source card if successful."""
    from engine.stack import StackObject
    from engine.zones import move_to_zone

    if not isinstance(stack_obj, StackObject):
        return None

    stack_items = game.stack._items  # noqa: SLF001
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            move_to_zone(game, stack_obj.source, Zone.STACK, Zone.GRAVEYARD)
            return stack_obj.source
    return None


class ManaSculpt(Instant):
    """Mana Sculpt — counterspell with a delayed Wizard rider."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. If you control a Wizard, add an amount of {C} equal "
            "to the amount of mana spent to cast that spell at the beginning of your "
            "next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        return any(
            getattr(stack_obj, "is_spell", True)
            and getattr(stack_obj, "source", None) is not self
            for stack_obj in game.stack.objects()
        )

    def get_targets(self, game: "GameState") -> list[Any]:
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        if controller is None:
            return

        target = _get_chosen_target(self)
        countered_card = _counter_spell(game, target)
        if countered_card is None:
            return

        controls_wizard = any(
            "Wizard" in getattr(permanent, "subtypes", set())
            for permanent in controller.zones[Zone.BATTLEFIELD].get_all()
        )
        mana_to_add = getattr(
            countered_card,
            "mana_spent_total",
            getattr(countered_card, "total_mana_spent", 0),
        )
        if not controls_wizard or mana_to_add <= 0:
            return

        register_delayed_next_main_phase_trigger(
            game,
            player=controller,
            source=object(),
            effect=lambda resolving_game: controller.mana_pool.add(
                ManaType.COLORLESS,
                mana_to_add,
            ),
        )
