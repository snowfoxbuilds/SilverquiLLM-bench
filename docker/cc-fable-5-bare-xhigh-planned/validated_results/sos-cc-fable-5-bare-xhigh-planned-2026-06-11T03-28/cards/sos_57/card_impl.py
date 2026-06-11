"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move its card to the graveyard.

    Mirrors fdn_48 (Refute).
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


def _controls_a_wizard(game: "GameState", player: Any) -> bool:
    return any(
        "Wizard" in getattr(obj, "subtypes", set())
        for obj in game.get_battlefield(player).get_all()
    )


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
            "Counter target spell. If you control a Wizard, add an amount "
            "of {C} equal to the amount of mana spent to cast that spell "
            "at the beginning of your next main phase.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target spell on the stack."""
        candidates = [
            so for so in game.stack.objects()
            if so.source is not self and getattr(so, "is_spell", True)
        ]
        if not candidates:
            return []
        return [TargetRequirement(
            filter_fn=lambda obj: getattr(obj, "source", None) is not self
            and getattr(obj, "is_spell", True),
            description="target spell",
            zone=Zone.STACK,
        )]

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", None) or []
        target = targets[0] if targets else None
        if target is None:
            return

        # Amount of mana actually spent to cast the countered spell —
        # read before the card changes zones.
        amount = getattr(target.source, "mana_spent", 0) or 0

        _counter_spell(game, target)

        controller = self.controller
        if controller is None or amount <= 0:
            return
        self._register_delayed_mana(game, controller, amount)

    @staticmethod
    def _register_delayed_mana(game: "GameState", controller: Any, amount: int) -> None:
        """One-shot delayed trigger: at the beginning of *controller*'s next
        main phase, if they control a Wizard, add {C} × *amount*.

        ENGINE LIMITATION: only precombat main phases are modeled (the
        engine has no postcombat-main event), so "next main phase" means
        the next precombat main.
        """
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        sentinel = object()

        def _condition(g: Any, event: Any) -> bool:
            return g.active_player is controller

        def _effect(g: "GameState") -> None:
            g.trigger_manager.unregister(sentinel)
            if _controls_a_wizard(g, controller):
                controller.mana_pool.add(ManaType.COLORLESS, amount)

        game.trigger_manager.register(TriggerRegistration(
            event_type=BeginningOfPrecombatMainTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=sentinel,
            controller=controller,
        ))
