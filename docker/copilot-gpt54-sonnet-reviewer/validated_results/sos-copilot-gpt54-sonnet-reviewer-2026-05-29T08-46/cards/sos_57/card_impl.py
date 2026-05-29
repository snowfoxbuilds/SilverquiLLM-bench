"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.casting import counter_spell
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _get_chosen_target(card: Any, index: int = 0) -> Any:
    """Return the chosen target at *index* if present."""
    chosen_targets = getattr(card, "chosen_targets", None)
    if chosen_targets and len(chosen_targets) > index:
        return chosen_targets[index]
    return None


def _is_spell_stack_object(obj: Any) -> bool:
    """Return whether *obj* is a spell on the stack."""
    return isinstance(obj, StackObject) and bool(getattr(obj, "is_spell", False))


def _controls_wizard(game: "GameState", player: "Player | None") -> bool:
    """Return whether *player* controls a Wizard."""
    if player is None:
        return False

    battlefield = game.get_battlefield(player)
    for permanent in battlefield.get_all():
        if isinstance(permanent, Creature) and "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


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
        return any(_is_spell_stack_object(stack_obj) for stack_obj in game.stack.objects())

    def get_targets(self, game: "GameState") -> list[Any]:
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=_is_spell_stack_object,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        target = _get_chosen_target(self)
        if not _is_spell_stack_object(target):
            return
        if not any(stack_obj is target for stack_obj in game.stack.objects()):
            return

        target_card = target.source
        mana_spent_total = int(getattr(target_card, "mana_spent_total", 0))
        counter_spell(game, target)

        controller = self.controller
        if not _controls_wizard(game, controller):
            return

        def _condition(current_game: "GameState") -> bool:
            return (
                controller is not None
                and current_game.active_player is controller
                and current_game.phase in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN)
                and current_game.step is None
            )

        def _effect(current_game: "GameState") -> None:
            if controller is None or mana_spent_total <= 0:
                return
            controller.mana_pool.add(ManaType.COLORLESS, mana_spent_total)

        game.schedule_delayed_action(_condition, _effect)
