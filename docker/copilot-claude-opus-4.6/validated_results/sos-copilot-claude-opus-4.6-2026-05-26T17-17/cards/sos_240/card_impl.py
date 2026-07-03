"""Card implementation for Vibrant Outburst."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class VibrantOutburst(Instant):
    """Vibrant Outburst — {U}{R} — Instant.

    Vibrant Outburst deals 3 damage to any target. Tap up to one target creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vibrant Outburst")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Vibrant Outburst deals 3 damage to any target. Tap up to one target creature.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Two targets: any target (damage) + creature (tap, optional)."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: True,
                description="any target",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="up to one target creature",
                zone=Zone.BATTLEFIELD,
                optional=True,
            ),
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Deal 3 damage to first target, tap second target if present."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        # First target: deal 3 damage
        target = chosen[0] if len(chosen) > 0 else None
        if target is not None:
            if hasattr(target, "damage_marked"):
                target.damage_marked += 3
            elif hasattr(target, "life"):
                target.lose_life(3)

        # Second target: tap creature (optional)
        tap_target = chosen[1] if len(chosen) > 1 else None
        if tap_target is not None:
            tap_target.is_tapped = True
