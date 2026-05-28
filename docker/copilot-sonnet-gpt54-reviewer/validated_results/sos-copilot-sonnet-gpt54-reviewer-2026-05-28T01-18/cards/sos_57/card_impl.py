"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack zone and move card to graveyard.

    Follows the established pattern from fdn_48 (Refute):
    1. Remove StackObject from game.stack._items
    2. Remove source card from controller's Zone.STACK (if present)
    3. Move source card to owner's graveyard
    """
    from engine.stack import StackObject as _StackObject

    if not isinstance(stack_obj, _StackObject):
        return

    card = stack_obj.source

    # Remove StackObject from the game stack
    stack_items = game.stack._items  # noqa: SLF001
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            break
    else:
        return  # wasn't on the stack

    # Remove card from caster's Zone.STACK (may not be there in tests)
    controller = stack_obj.controller
    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    # Move card to owner's graveyard
    owner = getattr(card, "owner", None) or controller
    if owner is not None:
        owner.zones[Zone.GRAVEYARD].add(card)


class ManaSculpt(Instant):
    """Mana Sculpt — {1}{U}{U} — Instant.

    Counter target spell. If you control a Wizard, at the beginning of
    your next main phase, add {C} equal to the countered spell's mana value.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        super().__init__(**kwargs)
        self.keywords = Keyword(0)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target spell (not ability) on the stack."""
        return [
            TargetRequirement(
                # Issue 4 fix: only spells (not triggered/activated abilities).
                # StackObjects from cast_spell do not set is_spell=False;
                # ability objects may set it to False.  Default True is correct
                # for cards on the stack.
                filter_fn=lambda obj: getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell; if controller has a Wizard, register mana trigger."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return

        stack_obj = chosen[0]
        source_card = stack_obj.source

        # Issue 1 fix: use mana_paid (set at cast time) when available;
        # fall back to mana_cost.cmc for StackObjects created directly in tests.
        mana_value = getattr(stack_obj, "mana_paid", 0)
        if mana_value == 0 and hasattr(source_card, "mana_cost") and source_card.mana_cost is not None:
            mana_value = source_card.mana_cost.cmc

        # Issue 2 fix: use shared helper that also clears the card from
        # the caster's Zone.STACK (not just game.stack._items).
        _counter_spell(game, stack_obj)

        # Check if controller controls a Wizard
        controller = self.controller
        if controller is None:
            return

        if not self._controls_wizard(game, controller):
            return

        # Issue 3 fix: one-shot trigger scoped to the controller's next main
        # phase.  The condition ensures it only fires when the active player IS
        # the controller.  The effect unregisters the trigger after it fires
        # once (one-shot).
        captured_mana_value = mana_value
        captured_controller = controller
        captured_source = self

        def _mana_effect(g: "GameState") -> None:
            for _ in range(captured_mana_value):
                captured_controller.mana_pool.add(ManaType.COLORLESS, 1)
            # One-shot: remove this trigger so it never fires again.
            g.trigger_manager.unregister(captured_source)

        trigger = TriggerRegistration(
            event_type=BeginningOfMainPhaseTriggeredEvent,
            condition=lambda g, e: g.active_player is captured_controller,
            effect=_mana_effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)

    def _controls_wizard(self, game: "GameState", player: Any) -> bool:
        """Return True if player controls at least one Wizard on the battlefield."""
        bf = game.get_battlefield(player)
        for obj in bf.get_all():
            subtypes = getattr(obj, "subtypes", set())
            if "Wizard" in subtypes:
                return True
        return False

