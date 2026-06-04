"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Remove a spell from the stack and move its card to the owner's graveyard."""
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break
    if not found:
        return

    card = stack_obj.source
    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)
    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)


def _controls_wizard(controller: "Player") -> bool:
    for c in controller.zones[Zone.BATTLEFIELD].get_all():
        if "Wizard" in getattr(c, "subtypes", set()):
            return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell.  If you control a Wizard, add {C} equal to the
    mana spent to cast that spell at the beginning of your next main phase.
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
        return any(obj.source is not self for obj in game.stack.objects())

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        if not any(obj.source is not self for obj in game.stack.objects()):
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: getattr(obj, "source", None) is not self,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else getattr(self, "_resolve_target", None)
        if target is None:
            return

        spell_card = getattr(target, "source", None)
        mana_spent = int(getattr(spell_card, "mana_spent", 0)) if spell_card else 0
        controller = self.controller

        _counter_spell(game, target)

        if controller is None or mana_spent <= 0:
            return
        if not _controls_wizard(controller):
            return
        self._register_delayed_mana(game, controller, mana_spent)

    def _register_delayed_mana(
        self, game: "GameState", controller: "Player", amount: int
    ) -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        marker = object()  # unique source so we can cleanly unregister
        state = {"fired": False}

        def _condition(g: "GameState", event: Any) -> bool:
            return not state["fired"] and getattr(event, "player", None) is controller

        def _effect(g: "GameState") -> None:
            state["fired"] = True
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            g.trigger_manager.unregister(marker)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=marker,
                controller=controller,
            )
        )
