"""Card implementation for Refute."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.card_queries import choose_object
from engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _counter_spell(game: "GameState", stack_obj: Any) -> None:
    """Counter a spell via the engine's shared stack-departure primitive.

    :func:`engine.stack.move_spell_off_stack` removes exactly *stack_obj* and
    puts an ordinary spell in its owner's graveyard — or exiles it when the
    cast stamped a departure replacement (a flashback cast, rule 702.34a).
    If *stack_obj* already left the stack, nothing happens (fizzle).
    """
    from engine.stack import StackObject, move_spell_off_stack

    if not isinstance(stack_obj, StackObject):
        return
    move_spell_off_stack(game, stack_obj)


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
        from engine.stack import StackObject

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
        from engine.stack import StackObject

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
        from engine.game import discard, draw_card

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
            chosen = choose_object(
                game, controller, cards_in_hand, "Choose a card to discard", source_card=self
            )
            if chosen is not None:
                discard(game, controller, chosen)
