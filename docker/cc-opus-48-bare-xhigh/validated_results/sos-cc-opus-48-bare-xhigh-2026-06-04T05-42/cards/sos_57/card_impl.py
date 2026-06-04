"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import MainPhaseBeganTriggeredEvent
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove its StackObject and move the card to its
    owner's graveyard."""
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
        owner.zones[Zone.GRAVEYARD].add(card)


def _controls_wizard(game: "GameState", controller: "Player") -> bool:
    if controller is None:
        return False
    for obj in game.get_battlefield(controller).get_all():
        if "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


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
        self.colors = ["U"]

    def can_cast(self, game: "GameState") -> bool:
        for stack_obj in game.stack.objects():
            if getattr(stack_obj, "source", None) is self:
                continue
            if getattr(stack_obj.source, "card_types", None):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        has_target = any(
            getattr(so, "source", None) is not self
            and getattr(so.source, "card_types", None)
            for so in game.stack.objects()
        )
        if not has_target:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: getattr(obj, "source", None) is not self
                and bool(getattr(getattr(obj, "source", None), "card_types", None)),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        target = _get_chosen_target(self, game)
        if target is None:
            return

        countered_card = getattr(target, "source", None)
        amount = int(getattr(countered_card, "mana_spent", 0) or 0)
        controller = self.controller

        _counter_spell(game, target)

        if amount > 0 and _controls_wizard(game, controller):
            self._setup_delayed_mana(game, controller, amount)

    def _setup_delayed_mana(
        self, game: "GameState", controller: "Player", amount: int
    ) -> None:
        from engine.triggers import TriggerRegistration

        sentinel = type("ManaSculptDelay", (), {"name": "Mana Sculpt"})()
        state = {"fired": False}

        def _condition(g: "GameState", event: MainPhaseBeganTriggeredEvent) -> bool:
            if state["fired"]:
                return False
            return getattr(event, "player", None) is controller

        def _effect(g: "GameState") -> None:
            if state["fired"]:
                return
            state["fired"] = True
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            g.trigger_manager.unregister(sentinel)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=MainPhaseBeganTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=sentinel,
                controller=controller,
            )
        )
