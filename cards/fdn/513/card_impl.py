"""Card implementation for QuickStudy."""

from __future__ import annotations


from engine.card import Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class QuickStudy(Instant):
    """Quick Study — {2}{U} — Draw two cards."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quick Study")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("rules_text", "Draw two cards.")
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """No targets — Quick Study doesn't target."""
        return []

    def on_resolve(self, game: GameState) -> None:
        """Draw 2 cards for the controller."""
        from engine.game import draw_card

        controller = self.controller
        if controller is not None:
            draw_card(game, controller)
            draw_card(game, controller)


__all__ = ["QuickStudy"]
