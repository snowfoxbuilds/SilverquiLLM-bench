"""Card implementation for Impractical Joke."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImpracticalJoke(Sorcery):
    """Impractical Joke — {R} — Sorcery.

    Damage can't be prevented this turn. Deals 3 damage to up to one
    target creature or planeswalker.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Impractical Joke")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: disable damage prevention, deal 3 to target."""
        # Damage can't be prevented this turn
        game.damage_prevention_disabled = True

        # Deal 3 damage to up to one target
        chosen = getattr(self, "chosen_targets", None)
        if chosen:
            target = chosen[0]
            if hasattr(target, "damage_taken"):
                target.damage_taken += 3
            else:
                target.damage_taken = 3

