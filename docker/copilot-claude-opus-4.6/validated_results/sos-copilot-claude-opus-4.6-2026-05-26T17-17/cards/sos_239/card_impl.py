"""Card implementation for Traumatic Critique."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TraumaticCritique(Instant):
    """Traumatic Critique — {X}{U}{R} — Instant.

    Traumatic Critique deals X damage to any target. Draw two cards, then discard a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Traumatic Critique")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Traumatic Critique deals X damage to any target. Draw two cards, then discard a card.",
        )
        super().__init__(**kwargs)
        self.x_value: int = 0

    def get_targets(self, game: "GameState") -> list:
        """Any target."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Deal X damage, draw 2, discard 1."""
        from engine.game import draw_card

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None

        controller = self.controller or self.owner
        x = getattr(self, "x_value", 0)

        # Deal X damage to target
        if target is not None and x > 0:
            if hasattr(target, "damage_marked"):
                target.damage_marked += x
            elif hasattr(target, "life"):
                target.lose_life(x)

        # Draw two cards
        if controller is not None:
            draw_card(game, controller)
            draw_card(game, controller)

            # Discard a card
            hand = controller.zones[Zone.HAND].get_all()
            if hand:
                card_to_discard = hand[-1]
                controller.zones[Zone.HAND].remove(card_to_discard)
                controller.zones[Zone.GRAVEYARD].add(card_to_discard)
