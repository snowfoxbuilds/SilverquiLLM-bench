"""Card implementation for Chase Inspiration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ChaseInspiration(Instant):
    """Chase Inspiration — {U} — Instant.

    Target creature you control gets +0/+3 and gains hexproof until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chase Inspiration")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature you control gets +0/+3 and gains hexproof until end of turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature you control."""
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "controller", None) is controller
                ),
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Give target +0/+3 and hexproof until end of turn."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # +0/+3 until end of turn
        if not hasattr(target, "_temp_power_bonus"):
            target._temp_power_bonus = 0
        if not hasattr(target, "_temp_toughness_bonus"):
            target._temp_toughness_bonus = 0
        target._temp_toughness_bonus += 3

        # Grant hexproof
        target.keywords = target.keywords | Keyword.HEXPROOF
