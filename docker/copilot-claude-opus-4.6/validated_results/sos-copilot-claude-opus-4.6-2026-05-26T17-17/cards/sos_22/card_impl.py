"""Card implementation for Interjection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Interjection(Instant):
    """Interjection — {W} — Instant.

    Target creature gets +2/+2 and gains first strike until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Interjection")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Give target creature +2/+2 and first strike until end of turn."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        # Apply +2/+2 temporary bonus
        target._temp_power_bonus = getattr(target, "_temp_power_bonus", 0) + 2
        target._temp_toughness_bonus = getattr(target, "_temp_toughness_bonus", 0) + 2

        # Grant first strike
        target.keywords = target.keywords | Keyword.FIRST_STRIKE
