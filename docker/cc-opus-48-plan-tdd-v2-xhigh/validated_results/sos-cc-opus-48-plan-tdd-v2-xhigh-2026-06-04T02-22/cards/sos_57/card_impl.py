"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

    SOS collector number 57.
    """

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
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self
                and getattr(obj, "source", None) is not self
                and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.stack import counter_spell

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return

        source_card = getattr(target, "source", None)
        amount = getattr(source_card, "mana_spent", None)
        if amount is None:
            mc = getattr(source_card, "mana_cost", None)
            amount = mc.cmc if mc is not None else 0

        if not counter_spell(game, target):
            return

        controller = self.controller
        if controller is None or amount <= 0:
            return
        if not self._controls_wizard(game, controller):
            return
        self._schedule_mana(game, controller, amount)

    @staticmethod
    def _controls_wizard(game: "GameState", controller: Any) -> bool:
        bf = game.get_battlefield(controller)
        for obj in bf.get_all():
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                continue
            if "Wizard" in getattr(obj, "subtypes", set()):
                return True
        return False

    @staticmethod
    def _schedule_mana(game: "GameState", controller: Any, amount: int) -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        sentinel = object()  # unique source handle for one-shot (un)registration

        def _condition(game: Any, event: Any) -> bool:
            return game.active_player is controller

        def _effect(game: "GameState") -> None:
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            game.trigger_manager.unregister(sentinel)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=sentinel,
                controller=controller,
            )
        )
