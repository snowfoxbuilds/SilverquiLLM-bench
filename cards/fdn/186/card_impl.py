"""Card implementation for EmbraceTheParadox."""

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



class EmbraceTheParadox(Instant):
    """Embrace the Paradox — {3}{G}{U} — Draw three cards.

    The "you may put a land card onto the battlefield tapped" part is
    not implemented; only the draw effect is.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Embrace the Paradox")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Draw three cards. You may put a land card from your hand "
            "onto the battlefield tapped.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import draw_card

        controller = self.controller
        if controller is not None:
            for _ in range(3):
                draw_card(game, controller)


__all__ = ["EmbraceTheParadox"]
