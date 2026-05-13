"""Card implementation for Cancel."""

from __future__ import annotations


from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    # Real pipeline: targets stored by cast_spell on the card
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    # Test backdoor: attribute set directly by test code
    return getattr(card, "_resolve_target", None)

def _counter_spell(game: GameState, stack_obj: Any) -> None:
    """Counter a spell — remove it from the stack and move the card to its owner's graveyard.

    Args:
        game: The current game state.
        stack_obj: The :class:`~engine.stack.StackObject` to counter.
    """
    from engine.stack import StackObject

    if not isinstance(stack_obj, StackObject):
        return

    card = stack_obj.source

    # Remove the stack object from the stack.
    # The stack stores items internally; we need to find and remove it.
    stack_items = game.stack._items  # noqa: SLF001 — internal access needed
    found = False
    for i, item in enumerate(stack_items):
        if item is stack_obj:
            stack_items.pop(i)
            found = True
            break

    # If the target was not on the stack, fizzle — do nothing.
    if not found:
        return

    # Move the card from the stack zone to the owner's graveyard.
    controller = stack_obj.controller
    owner = getattr(card, "owner", controller)

    # Remove from the controller's stack zone.
    if controller is not None:
        stack_zone = controller.zones[Zone.STACK]
        if stack_zone.contains(card):
            stack_zone.remove(card)

    # Add to owner's graveyard.
    if owner is not None:
        graveyard = owner.zones[Zone.GRAVEYARD]
        graveyard.add(card)


class Cancel(Instant):
    """Cancel — {1}{U}{U} — Counter target spell."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cancel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("rules_text", "Counter target spell.")
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        """Cannot cast Cancel unless there is a spell on the stack to counter."""
        for stack_obj in game.stack.objects():
            if stack_obj.source is not self:
                return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        """Target any spell on the stack."""
        targets: list[Any] = []
        for stack_obj in game.stack.objects():
            # Don't target self (Cancel can't counter itself).
            if stack_obj.source is not self:
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Counter the target spell — remove from stack, move to graveyard."""
        target = _get_chosen_target(self, game)
        if target is None:
            return
        _counter_spell(game, target)


__all__ = ["Cancel"]
