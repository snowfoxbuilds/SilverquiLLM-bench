"""Card implementation for TemporalManipulation."""

from __future__ import annotations


from engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
from typing import TYPE_CHECKING, Any



class TemporalManipulation(Sorcery):
    """Temporal Manipulation — {3}{U}{U} — Sorcery

    Take an extra turn after this one.

    SPG collector number 82.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Temporal Manipulation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Take an extra turn after this one.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        """Grant the controller an extra turn."""
        controller = self.controller or self.owner
        if controller is None:
            return
        # Find the controller's player index
        player_index = None
        for i, p in enumerate(game.players):
            if p is controller:
                player_index = i
                break
        if player_index is not None:
            game.extra_turns.append(player_index)


__all__ = ["TemporalManipulation"]
