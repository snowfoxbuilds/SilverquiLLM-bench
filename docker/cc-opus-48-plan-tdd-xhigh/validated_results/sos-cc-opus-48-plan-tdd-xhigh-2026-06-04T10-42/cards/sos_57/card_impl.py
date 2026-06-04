"""Card implementation for Mana Sculpt (SOS #57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    """Return the first chosen target for a spell, if any."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell: remove it from the stack and put the card in its
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


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C} equal
    to the amount of mana spent to cast that spell at the beginning of your
    next main phase.

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

    def _spell_targets(self, game: "GameState") -> list[Any]:
        return [
            so
            for so in game.stack.objects()
            if so.source is not self and getattr(so, "is_spell", True)
        ]

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a spell on the stack to counter."""
        return bool(self._spell_targets(game))

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target a spell on the stack."""
        if not self._spell_targets(game):
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
        """Counter the target spell; if a Wizard is controlled, schedule the
        deferred {C} for the controller's next main phase."""
        target = _get_chosen_target(self)
        if target is None:
            return

        # Capture data before the spell leaves the stack. "Mana spent to cast"
        # is modelled by the spell's converted mana cost.
        source_card = getattr(target, "source", None)
        cost = getattr(source_card, "mana_cost", None)
        amount = cost.cmc if cost is not None else 0
        controls_wizard = self._controls_wizard()

        _counter_spell(game, target)

        if controls_wizard and amount > 0:
            self._register_deferred_mana(game, amount)

    def _controls_wizard(self) -> bool:
        ctrl = self.controller
        if ctrl is None:
            return False
        for obj in ctrl.zones[Zone.BATTLEFIELD].get_all():
            if "Wizard" in getattr(obj, "subtypes", set()):
                return True
        return False

    def _register_deferred_mana(self, game: "GameState", amount: int) -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller

        def _condition(game: Any, event: Any) -> bool:
            return getattr(game, "active_player", None) is source.controller

        def _effect(game: Any) -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, amount)
            # One-shot: fire only on the next main phase, then stop.
            game.trigger_manager.unregister(source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
