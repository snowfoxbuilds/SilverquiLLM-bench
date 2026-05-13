"""Card implementation for VisionarysDance."""

from __future__ import annotations


from engine.card import Artifact, Creature, Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any
import math

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class VisionarysDance(Sorcery):
    """Visionary's Dance — {5}{U}{R} — Create two 3/3 blue and red Elemental
    creature tokens with flying.

    The channel ability is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Visionary's Dance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Create two 3/3 blue and red Elemental creature tokens with "
            "flying.\n{2}, Discard this card: Look at the top two cards of "
            "your library. Put one into your hand and the other into your "
            "graveyard.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        for _ in range(2):
            token = Creature(
                name="Elemental",
                base_power=3,
                base_toughness=3,
                subtypes={"Elemental"},
                keywords=Keyword.FLYING,
            )
            create_token(game, controller, token)


__all__ = ["VisionarysDance"]
