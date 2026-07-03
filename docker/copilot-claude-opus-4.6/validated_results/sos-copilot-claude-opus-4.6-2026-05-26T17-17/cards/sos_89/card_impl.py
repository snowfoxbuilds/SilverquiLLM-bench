"""Card implementation for Masterful Flourish."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MasterfulFlourish(Instant):
    """{B} Instant — Target creature you control gets +1/+0 and gains
    indestructible until end of turn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Masterful Flourish")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature you control",
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
        target.modified_power = getattr(target, "modified_power", 0) + 1
        target.keywords = getattr(target, "keywords", Keyword(0)) | Keyword.INDESTRUCTIBLE
