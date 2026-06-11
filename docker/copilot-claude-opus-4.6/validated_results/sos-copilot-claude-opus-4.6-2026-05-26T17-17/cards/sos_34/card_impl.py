"""Card implementation for Stand Up for Yourself."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class StandUpForYourself(Instant):
    """Stand Up for Yourself — {2}{W} — Instant.

    Destroy target creature with power 3 or greater.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stand Up for Yourself")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target creature with power 3 or greater.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature with power 3 or greater."""
        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            if CardType.CREATURE not in card_types:
                return False
            power = getattr(obj, "power", None)
            if power is None:
                power = getattr(obj, "base_power", 0)
            return power >= 3

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target creature with power 3 or greater",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Destroy the target creature."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return
        from engine.game import destroy
        destroy(game, target)
