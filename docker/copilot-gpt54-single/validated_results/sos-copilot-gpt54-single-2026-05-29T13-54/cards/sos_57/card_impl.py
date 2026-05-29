"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return whether *player* controls a Wizard."""
    if player is None:
        return False
    for permanent in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


def _get_chosen_target(card: Any) -> Any:
    """Return the first chosen target, if any."""
    chosen_targets = getattr(card, "chosen_targets", None)
    if chosen_targets:
        return chosen_targets[0]
    return None


@dataclass
class _DelayedManaSculptTrigger:
    """Identity-bearing source object for Mana Sculpt's delayed trigger."""

    controller: Any
    mana_amount: int


class ManaSculpt(Instant):
    """Mana Sculpt — counter a spell, then possibly add delayed colorless mana."""

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
        """Mana Sculpt requires a spell to be on the stack."""
        return any(getattr(stack_obj, "is_spell", False) for stack_obj in game.stack.objects())

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a spell on the stack."""
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, StackObject) and getattr(obj, "is_spell", False),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell and set up the delayed mana trigger if needed."""
        from engine.countering import counter_spell
        from engine.triggers import TriggerRegistration

        target = _get_chosen_target(self)
        if not isinstance(target, StackObject):
            return
        if target not in game.stack.objects():
            return

        mana_amount = max(0, int(getattr(target, "total_mana_spent", 0) or 0))
        counter_spell(game, target)

        controller = self.controller
        if not _controls_wizard(game, controller) or mana_amount <= 0:
            return

        delayed_source = _DelayedManaSculptTrigger(controller=controller, mana_amount=mana_amount)

        def _condition(current_game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            if event.player is not controller:
                return False
            current_game.trigger_manager.unregister(delayed_source)
            return True

        def _effect(current_game: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, mana_amount)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=delayed_source,
                controller=controller,
            )
        )
