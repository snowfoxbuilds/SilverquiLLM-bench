"""Card implementation for Last Gasp."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LastGasp(Instant):
    """{1}{B} Instant — Target creature gets -3/-3 until end of turn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Last Gasp")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return
        target.modified_power = getattr(target, "modified_power", 0) - 3
        target.modified_toughness = getattr(target, "modified_toughness", 0) - 3
