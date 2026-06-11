"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard.

    Mirrors fdn_48 (Refute): pop the StackObject from the stack and move
    the card from the stack zone to its owner's graveyard.
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
            "of {C} equal to the amount of mana spent to cast that spell at "
            "the beginning of your next main phase.",
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
        targets = []
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: getattr(obj, "source", None) is not self
                and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target; set up the delayed mana for your next main phase."""
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        from engine.triggers import TriggerRegistration

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        # Single-target spell fizzles if the target is gone/illegal.
        if target is None:
            return

        # Amount of mana actually spent to cast that spell (recorded at
        # cast time; 0 for free casts and spell copies).
        amount = getattr(getattr(target, "source", None), "mana_spent", 0) or 0

        _counter_spell(game, target)

        controller = self.controller
        if controller is None or amount <= 0:
            return

        # Delayed one-shot trigger at the beginning of your next main phase.
        # ENGINE LIMITATION (deliberate): the engine only fires a
        # beginning-of-main event for the precombat main phase, so "your
        # next main phase" is treated as your next precombat main phase.
        marker = object()
        state = {"fired": False}

        def _cond(g: Any, event: Any) -> bool:
            if state["fired"]:
                return False
            if g.active_player is not controller:
                return False
            state["fired"] = True
            return True

        def _eff(g: "GameState") -> None:
            g.trigger_manager.unregister(marker)
            controls_wizard = any(
                "Wizard" in getattr(perm, "subtypes", set())
                for perm in controller.zones[Zone.BATTLEFIELD].get_all()
            )
            if controls_wizard:
                controller.mana_pool.add(ManaType.COLORLESS, amount)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_cond,
                effect=_eff,
                source=marker,
                controller=controller,
            )
        )
