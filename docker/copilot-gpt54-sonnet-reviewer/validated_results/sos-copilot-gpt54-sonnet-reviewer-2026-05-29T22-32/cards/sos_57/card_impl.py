"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.game_state import DelayedEffect
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _is_spell_on_stack(obj: Any) -> bool:
    source = getattr(obj, "source", None)
    return source is not None and hasattr(source, "card_types")


def _controls_wizard(game: "GameState", player: Any) -> bool:
    if player is None:
        return False
    for obj in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


def _counter_spell(game: "GameState", stack_obj: Any) -> Any | None:
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return None

    for index, item in enumerate(game.stack._items):  # noqa: SLF001
        if item is stack_obj:
            game.stack._items.pop(index)  # noqa: SLF001
            card = stack_obj.source
            move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
            return card
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
        return any(
            _is_spell_on_stack(stack_obj) and getattr(stack_obj, "source", None) is not self
            for stack_obj in game.stack.objects()
        )

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=_is_spell_on_stack,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        target = _get_chosen_target(self)
        if target is None:
            return

        controlled_wizard = _controls_wizard(game, controller)
        countered_card = _counter_spell(game, target)

        if not controlled_wizard or controller is None or countered_card is None:
            return

        mana_amount = max(0, int(getattr(countered_card, "mana_spent_amount", 0) or 0))
        if mana_amount <= 0:
            return

        def _next_main_phase_condition(current_game: "GameState") -> bool:
            return (
                current_game.active_player is controller
                and current_game.step is None
                and current_game.phase in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN)
            )

        def _add_colorless(current_game: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, mana_amount)

        game.add_delayed_effect(DelayedEffect(
            condition=_next_main_phase_condition,
            effect=_add_colorless,
        ))
