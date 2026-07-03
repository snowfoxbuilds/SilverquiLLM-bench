"""Card implementation for Fractalize."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Color, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Fractalize(Instant):
    """Fractalize — {X}{U} Instant.

    Until end of turn, target creature becomes a green and blue Fractal
    with base power and toughness each equal to X plus 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractalize")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}"))
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
        targets = getattr(self, "chosen_targets", None)
        if not targets:
            return
        target = targets[0]
        x = getattr(self, "x_value", 0)
        new_pt = x + 1

        target.base_power = new_pt
        target.base_toughness = new_pt
        target.modified_power = new_pt
        target.modified_toughness = new_pt
        target.colors = {Color.GREEN, Color.BLUE}
        target.subtypes = {"Fractal"}
