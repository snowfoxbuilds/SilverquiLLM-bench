"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> int:
    """Counter a spell — remove it from the stack and move its card to the
    graveyard.

    Returns the mana value of the countered spell (``0`` if nothing was
    actually countered), used to size the delayed mana.
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return 0

    card = stack_obj.source
    stack_items = game.stack._items  # noqa: SLF001
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    if not found:
        return 0

    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)

    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is not None:
        return mana_cost.cmc
    return 0


def _controls_wizard(player: Any) -> bool:
    """Return ``True`` if *player* controls a permanent with the Wizard subtype."""
    if player is None:
        return False
    bf = player.zones[Zone.BATTLEFIELD]
    for obj in bf.get_all():
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
            "Counter target spell. If you control a Wizard, add an amount of "
            "{C} equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase.",
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

    def get_targets(self, game: "GameState") -> list:
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
                filter_fn=lambda obj: obj is not self
                and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell; if you control a Wizard, schedule the
        delayed colorless mana for your next main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        target = _get_chosen_target(self, game)
        if target is None:
            return

        mana_value = _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return
        if not _controls_wizard(controller):
            return
        if mana_value <= 0:
            return

        # One-shot delayed trigger fired at the beginning of the
        # controller's next main phase. ``marker`` gives the registration a
        # unique identity so the effect can unregister itself after firing.
        marker = object()

        def _condition(g: "GameState", event: Any, _c: Any = controller) -> bool:
            return getattr(event, "player", None) is _c

        def _effect(
            g: "GameState",
            _c: Any = controller,
            _amount: int = mana_value,
            _src: Any = marker,
        ) -> None:
            _c.mana_pool.add(ManaType.COLORLESS, _amount)
            g.trigger_manager.unregister(_src)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=marker,
                controller=controller,
            )
        )
