"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.casting import counter_stack_object
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    """Return Mana Sculpt's chosen spell target, if any."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


class ManaSculpt(Instant):
    """Mana Sculpt — counter a spell and delay colorless mana if you control a Wizard."""

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
        """Mana Sculpt needs another spell on the stack to target."""
        return any(
            getattr(stack_obj, "is_spell", True) and getattr(stack_obj, "source", None) is not self
            for stack_obj in game.stack.objects()
        )

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target exactly one spell on the stack."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the chosen spell and, if appropriate, delay colorless mana."""
        target = _get_chosen_target(self)
        if target is None:
            return

        target_card = getattr(target, "source", None)
        mana_spent = getattr(target_card, "mana_spent", 0)
        controller = self.controller

        if not counter_stack_object(game, target):
            return

        if controller is None or mana_spent <= 0:
            return
        if not any("Wizard" in getattr(obj, "subtypes", set()) for obj in game.get_battlefield(controller).get_all()):
            return

        def _add_mana_next_main_phase(current_game: "GameState") -> bool:
            if current_game.active_player is not controller:
                return True
            if current_game.phase not in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN):
                return True
            controller.mana_pool.add(ManaType.COLORLESS, mana_spent)
            return False

        game.register_phase_transition_callback(_add_mana_next_main_phase)
