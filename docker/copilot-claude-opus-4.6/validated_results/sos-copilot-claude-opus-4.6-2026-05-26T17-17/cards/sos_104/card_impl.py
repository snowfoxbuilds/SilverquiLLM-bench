"""Card implementation for Wander Off."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WanderOff(Instant):
    """Wander Off — {3}{B} — Instant.

    Exile target creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wander Off")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature on the battlefield."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Exile the targeted creature."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target = chosen[0]
        if target is None:
            return

        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                bf.remove(target)
                card_owner = getattr(target, "owner", player)
                exile = game.get_exile(card_owner)
                exile.add(target)
                return
