"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfPrecombatMainTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from the stack and move its card to graveyard."""
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


def _controls_wizard(player: Any) -> bool:
    for c in player.zones[Zone.BATTLEFIELD].get_all():
        if CardType.CREATURE in getattr(c, "card_types", set()) and "Wizard" in getattr(
            c, "subtypes", set()
        ):
            return True
    return False


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C} equal to
    the amount of mana spent to cast that spell at the beginning of your next
    main phase.

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
        """Only castable with another spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        for stack_obj in game.stack.objects():
            if stack_obj.source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                return [
                    TargetRequirement(
                        filter_fn=lambda obj: obj is not self
                        and getattr(obj, "is_spell", True),
                        description="target spell",
                        zone=Zone.STACK,
                    )
                ]
        return []

    def on_resolve(self, game: "GameState") -> None:
        target = _get_chosen_target(self)
        if target is None:
            return  # single-target spell fizzles if target is illegal
        # "the amount of mana spent to cast that spell" — recorded at cast time.
        amount = getattr(getattr(target, "source", None), "mana_spent", 0) or 0
        _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return
        # Set up the delayed mana.  Register a one-shot trigger on the
        # beginning-of-precombat-main event (E2), stamped with the cast turn so
        # it fires at the controller's *next* main phase.  The "if you control a
        # Wizard" check is evaluated when the delayed ability fires.
        if amount <= 0:
            return
        cast_turn = getattr(game, "turn_number", 0)
        self._register_delayed_mana(game, controller, amount, cast_turn)

    def _register_delayed_mana(
        self, game: "GameState", controller: Any, amount: int, cast_turn: int
    ) -> None:
        from engine.triggers import TriggerRegistration

        # Unique source so the one-shot can unregister exactly itself.
        delayed_source = object()

        def _condition(g: "GameState", event: Any) -> bool:
            return (
                getattr(g, "active_player", None) is controller
                and getattr(g, "turn_number", 0) > cast_turn
            )

        def _effect(g: "GameState") -> None:
            if _controls_wizard(controller):
                controller.mana_pool.add(ManaType.COLORLESS, amount)
            # One-shot: remove regardless of whether mana was added.
            g.trigger_manager.unregister(delayed_source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfPrecombatMainTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=delayed_source,
                controller=controller,
            )
        )
