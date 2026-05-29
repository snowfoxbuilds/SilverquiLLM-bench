"""Card implementation for Mana Sculpt (sos_57)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
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
        self._pending_mana: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Counter the target spell, optionally schedule mana refund."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return

        target_stack_obj = chosen[0]
        if target_stack_obj is None:
            return

        # Get the CMC of the countered spell before removing it
        source_card = getattr(target_stack_obj, "source", None)
        mana_value = 0
        if source_card is not None:
            mc = getattr(source_card, "mana_cost", None)
            if mc is not None:
                mana_value = mc.cmc

        # Counter the spell: remove from stack and send source to graveyard
        _counter_spell(game, target_stack_obj)

        # If controller has a Wizard, schedule mana refund
        controller = self.controller
        if controller is not None and mana_value > 0:
            if _controls_wizard(game, controller):
                self._pending_mana = mana_value
                _register_mana_trigger(game, self, controller, mana_value)


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Remove *stack_obj* from the stack and move its source to graveyard."""
    # Remove from stack
    if stack_obj in game.stack._items:
        game.stack._items.remove(stack_obj)

    # Move the source card to its owner's graveyard
    source = getattr(stack_obj, "source", None)
    if source is None:
        return

    owner = getattr(source, "owner", None)
    controller = getattr(source, "controller", owner)
    if owner is None:
        owner = controller
    if owner is None:
        return

    # Find and remove from stack zone
    stack_zone = None
    for p in game.players:
        if p.zones[Zone.STACK].contains(source):
            stack_zone = p.zones[Zone.STACK]
            break

    if stack_zone is not None:
        stack_zone.remove(source)

    # Move to graveyard
    owner.zones[Zone.GRAVEYARD].add(source)


def _controls_wizard(game: "GameState", player: Any) -> bool:
    """Return True if player controls a Wizard on the battlefield."""
    for obj in game.get_battlefield(player).get_all():
        if "Wizard" in getattr(obj, "subtypes", set()):
            return True
    return False


def _register_mana_trigger(
    game: "GameState", source: Any, controller: Any, amount: int
) -> None:
    """Register a one-shot trigger to add {C} at beginning of next main phase."""
    fired = [False]

    def condition(g: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
        return not fired[0] and event.player is controller

    def effect(g: "GameState") -> None:
        if not fired[0]:
            fired[0] = True
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            game.trigger_manager.unregister(source)

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=condition,
            effect=effect,
            source=source,
            controller=controller,
        )
    )
