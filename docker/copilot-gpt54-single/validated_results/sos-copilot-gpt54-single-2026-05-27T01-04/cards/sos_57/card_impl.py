"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.casting import counter_stack_spell
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return whether *player* currently controls a Wizard permanent."""
    if player is None:
        return False
    for permanent in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


def _is_spell_stack_object(obj: Any) -> bool:
    """Return whether *obj* is a spell stack object."""
    return isinstance(obj, StackObject) and getattr(obj, "is_spell", True)


class ManaSculpt(Instant):
    """Mana Sculpt — counterspell with a delayed Wizard mana rider."""

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
        """Mana Sculpt needs another spell on the stack to target."""
        return any(
            _is_spell_stack_object(stack_obj) and getattr(stack_obj, "source", None) is not self
            for stack_obj in game.stack.objects()
        )

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Mana Sculpt targets a spell on the stack."""
        if not any(
            _is_spell_stack_object(stack_obj) and getattr(stack_obj, "source", None) is not self
            for stack_obj in game.stack.objects()
        ):
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: _is_spell_stack_object(obj),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell and optionally schedule delayed colorless mana."""
        chosen_targets = getattr(self, "chosen_targets", [])
        if not chosen_targets:
            return

        target = chosen_targets[0]
        if not _is_spell_stack_object(target):
            return
        if target not in game.stack._items:  # noqa: SLF001
            return

        mana_amount = int(
            getattr(
                target,
                "mana_spent_to_cast",
                getattr(getattr(target, "source", None), "mana_spent_to_cast", 0),
            )
            or 0
        )
        controller = self.controller
        should_add_mana = _controls_wizard(game, controller) and controller is not None and mana_amount > 0

        counter_stack_spell(game, target)

        if not should_add_mana:
            return

        def _delayed_action(current_game: GameState) -> bool:
            if (
                current_game.active_player is controller
                and current_game.step is None
                and current_game.phase in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN)
            ):
                controller.mana_pool.add(ManaType.COLORLESS, mana_amount)
                return True
            return False

        game.add_delayed_action(_delayed_action)
