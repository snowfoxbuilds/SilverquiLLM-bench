"""Card implementation for Essence Scatter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EssenceScatter(Instant):
    """Essence Scatter — {1}{U} — Instant.

    Counter target creature spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Essence Scatter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)

    def is_valid_target(self, game: "GameState", target: Any) -> bool:
        """Return True if target is a creature spell (on the stack)."""
        card_types = getattr(target, "card_types", set())
        return CardType.CREATURE in card_types

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature spell."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Counter target creature spell (move it to its owner's graveyard)."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # Move the countered spell to its owner's graveyard
        owner = getattr(target, "owner", None)
        if owner is None:
            return

        # Remove from stack zone if present
        stack_zone = owner.zones[Zone.STACK]
        if stack_zone.contains(target):
            stack_zone.remove(target)

        # Also check controller's stack zone
        controller = getattr(target, "controller", None)
        if controller and controller is not owner:
            ctrl_stack = controller.zones[Zone.STACK]
            if ctrl_stack.contains(target):
                ctrl_stack.remove(target)

        # Move to owner's graveyard
        owner.zones[Zone.GRAVEYARD].add(target)
