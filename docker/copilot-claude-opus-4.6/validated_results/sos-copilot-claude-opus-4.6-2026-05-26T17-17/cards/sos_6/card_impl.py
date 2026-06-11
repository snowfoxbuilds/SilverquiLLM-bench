"""Card implementation for Ajani's Response."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AjanisResponse(Instant):
    """{4}{W} Instant — Destroy target creature. Costs {3} less if targeting tapped creature."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ajani's Response")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def cost_reduction(self, game: "GameState") -> int:
        chosen = getattr(self, "chosen_targets", None)
        if chosen and len(chosen) > 0:
            target = chosen[0]
            if getattr(target, "is_tapped", False):
                return 3
        return 0

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        from engine.game import destroy
        destroy(game, target)
