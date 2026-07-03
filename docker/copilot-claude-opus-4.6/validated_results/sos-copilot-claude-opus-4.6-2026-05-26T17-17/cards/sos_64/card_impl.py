"""Card implementation for Procrastinate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Procrastinate(Sorcery):
    """Procrastinate — {X}{U} — Sorcery.

    Tap target creature. Put twice X stun counters on it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Procrastinate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}"))
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
        """Tap target creature and put 2X stun counters on it."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        # Tap the creature
        target.tapped = True
        # Put 2*X stun counters
        x = getattr(self, "x_value", 0)
        stun = 2 * x
        if stun > 0:
            current = getattr(target, "stun_counters", 0)
            target.stun_counters = current + stun
