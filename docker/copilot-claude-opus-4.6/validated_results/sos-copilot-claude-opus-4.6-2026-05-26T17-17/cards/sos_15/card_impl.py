"""Card implementation for Erode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Erode(Instant):
    """Erode — {W} — Instant.

    Destroy target creature or planeswalker. Its controller may search
    their library for a basic land card, put it onto the battlefield
    tapped, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Erode")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature or planeswalker."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: bool(
                    {CardType.CREATURE, CardType.PLANESWALKER}
                    & getattr(obj, "card_types", set())
                ),
                description="target creature or planeswalker",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Destroy target creature or planeswalker."""
        from engine.game import destroy

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target = chosen[0]
        if target is None:
            return

        # Find target's controller
        controller = getattr(target, "controller", None)
        if controller is None:
            return

        # Check target is still on battlefield
        bf = game.get_battlefield(controller)
        if not bf.contains(target):
            return

        destroy(game, target)
