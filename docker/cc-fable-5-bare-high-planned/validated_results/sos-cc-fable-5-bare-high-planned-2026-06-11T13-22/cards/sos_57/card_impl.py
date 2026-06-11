"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard.

    Mirrors fdn_48 (Refute).  Limitation: bypasses move_to_zone, so
    graveyard-replacement effects do not apply to countered spells.
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
        owner.zones[Zone.GRAVEYARD].add(card)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    return any(
        CardType.CREATURE in getattr(c, "card_types", set())
        and "Wizard" in getattr(c, "subtypes", set())
        for c in game.get_battlefield(player).get_all()
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

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        targets = [
            so for so in game.stack.objects()
            if so.source is not self and getattr(so, "is_spell", True)
        ]
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
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return  # fizzles

        # Amount actually paid for the countered spell (0 for free casts).
        amount = getattr(target.source, "mana_spent", 0)

        _counter_spell(game, target)

        controller = self.controller
        if controller is None or amount <= 0:
            return
        # "If you control a Wizard" — checked as this spell resolves.
        if not _controls_wizard(game, controller):
            return
        _register_delayed_mana(game, controller, amount)


def _register_delayed_mana(game: "GameState", controller: Any, amount: int) -> None:
    """One-shot: at the beginning of *controller*'s next precombat main
    phase, add {C} × *amount*.

    Limitation: "your next main phase" is modelled as your next PREcombat
    main phase (the only main-phase event the engine fires).
    """
    from engine.events import BeginningOfPrecombatMainTriggeredEvent
    from engine.triggers import TriggerRegistration

    marker = object()  # unique source so unregistering is precise

    def _condition(game: Any, event: Any) -> bool:
        return game.active_player is controller

    def _effect(game: "GameState") -> None:
        controller.mana_pool.add(ManaType.COLORLESS, amount)
        game.trigger_manager.unregister(marker)  # one-shot

    game.trigger_manager.register(TriggerRegistration(
        event_type=BeginningOfPrecombatMainTriggeredEvent,
        condition=_condition,
        effect=_effect,
        source=marker,
        controller=controller,
    ))
