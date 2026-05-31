"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _controls_wizard(game: "GameState", player: Any) -> bool:
    battlefield = game.get_battlefield(player)
    for permanent in battlefield.get_all():
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


def _counter_spell(game: "GameState", stack_obj: Any) -> bool:
    from engine.stack import StackObject
    from engine.zones import move_to_zone

    if not isinstance(stack_obj, StackObject):
        return False

    for index, item in enumerate(game.stack._items):  # noqa: SLF001
        if item is not stack_obj:
            continue
        game.stack._items.pop(index)  # noqa: SLF001
        move_to_zone(game, stack_obj.source, Zone.STACK, Zone.GRAVEYARD)
        return True

    return False


class ManaSculpt(Instant):
    """Mana Sculpt — counter a spell and refund colorless mana next main."""

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
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", False):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self and getattr(obj, "is_spell", False),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        target = _get_chosen_target(self)
        if target is None:
            return

        mana_spent = getattr(target, "mana_spent", 0)
        if not _counter_spell(game, target):
            return

        controller = self.controller
        if controller is None or not _controls_wizard(game, controller):
            return

        game.schedule_for_next_main_phase(
            controller,
            lambda current_game: controller.mana_pool.add(ManaType.COLORLESS, mana_spent),
        )
