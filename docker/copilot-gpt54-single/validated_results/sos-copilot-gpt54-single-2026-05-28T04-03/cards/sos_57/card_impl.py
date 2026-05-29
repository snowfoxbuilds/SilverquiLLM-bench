"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.casting import counter_stack_object
from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _get_chosen_target(card: Any) -> Any:
    """Return the first chosen target for *card*, if any."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _is_spell_stack_object(stack_obj: Any) -> bool:
    """Return ``True`` if *stack_obj* represents a spell on the stack."""
    if not isinstance(stack_obj, StackObject):
        return False
    source = getattr(stack_obj, "source", None)
    if CardType.LAND in getattr(source, "card_types", set()):
        return False
    return getattr(stack_obj, "is_spell", True)


def _controls_wizard(game: "GameState", player: "Player | None") -> bool:
    """Return ``True`` if *player* controls a Wizard permanent."""
    if player is None:
        return False
    for permanent in game.get_battlefield(player).get_all():
        if CardType.CREATURE not in getattr(permanent, "card_types", set()):
            continue
        if "Wizard" in getattr(permanent, "subtypes", set()):
            return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — counter a spell and defer colorless mana to next main."""

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
        """Mana Sculpt needs another spell on the stack to target."""
        return any(
            _is_spell_stack_object(stack_obj) and getattr(stack_obj, "source", None) is not self
            for stack_obj in game.stack.objects()
        )

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a spell on the stack."""
        if not self.can_cast(game):
            return []
        return [
            TargetRequirement(
                filter_fn=_is_spell_stack_object,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def _register_delayed_mana_trigger(
        self,
        game: "GameState",
        controller: "Player",
        amount: int,
    ) -> None:
        """Register the one-shot delayed trigger for the next main phase."""
        trigger_source = object()

        def _condition(_game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return event.player is controller

        def _effect(_game: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            _game.trigger_manager.unregister(trigger_source)

        def _stack_object_factory(
            _game: "GameState",
            _event: BeginningOfMainPhaseTriggeredEvent,
            _trigger: TriggerRegistration,
        ) -> StackObject:
            return StackObject(
                source=self,
                controller=controller,
                on_resolve=_effect,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=trigger_source,
                controller=controller,
                stack_object_factory=_stack_object_factory,
            )
        )

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell and, with a Wizard, defer colorless mana."""
        target = _get_chosen_target(self)
        if target is None or not isinstance(target, StackObject):
            return

        target_spell = getattr(target, "source", None)
        mana_spent = int(getattr(target_spell, "mana_spent_to_cast", 0) or 0)

        if not counter_stack_object(game, target):
            return

        controller = self.controller
        if controller is None:
            return
        if not _controls_wizard(game, controller):
            return

        self._register_delayed_mana_trigger(game, controller, mana_spent)
