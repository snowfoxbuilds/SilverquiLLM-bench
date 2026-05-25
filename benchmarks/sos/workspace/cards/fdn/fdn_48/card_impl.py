"""Card implementation for Refute."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell — remove from stack and move card to graveyard."""
    from benchmarks.sos.workspace.engine.stack import StackObject

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


class Refute(Instant):
    """Refute — {1}{U}{U} — Instant.

    Counter target spell. Draw a card, then discard a card.

    FDN collector number 48.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Refute")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Counter target spell. Draw a card, then discard a card.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Cannot cast unless there's a spell on the stack to counter."""
        from benchmarks.sos.workspace.engine.stack import StackObject

        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            # Only target spells (not triggered/activated abilities)
            if getattr(stack_obj, "is_spell", True):
                return True
        return False

    def get_targets(self, game: "GameState") -> list:
        """Target spell on the stack."""
        from benchmarks.sos.workspace.engine.stack import StackObject

        targets = []
        for stack_obj in game.stack.objects():
            source = stack_obj.source
            if source is self:
                continue
            if getattr(stack_obj, "is_spell", True):
                targets.append(stack_obj)
        if not targets:
            return []
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj is not self and getattr(obj, "is_spell", True),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target spell, then draw a card, then discard a card."""
        from benchmarks.sos.workspace.engine.game import discard, draw_card

        target = _get_chosen_target(self, game)
        # Single-target spell fizzles if target is illegal
        if target is None:
            return
        if target is not None:
            _counter_spell(game, target)

        controller = self.controller
        if controller is None:
            return

        # Draw a card
        draw_card(game, controller)

        # Discard a card
        hand = controller.zones[Zone.HAND]
        cards_in_hand = list(hand.get_all())
        if cards_in_hand:
            try:
                chosen = controller.choose_card(
                    cards_in_hand, "Choose a card to discard"
                )
            except Exception:
                chosen = cards_in_hand[0] if cards_in_hand else None
            if chosen is not None:
                discard(game, controller, chosen)
