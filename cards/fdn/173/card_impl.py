"""Card implementation for Exsanguinate."""

from __future__ import annotations


from engine.card import Creature, Instant, Mode, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, "controller", None)


class Exsanguinate(Sorcery):
    """Exsanguinate — {X}{B}{B}

    Each opponent loses X life. You gain life equal to the life lost
    this way.

    FDN collector number 173.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Exsanguinate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Each opponent loses X life. You gain life equal to the life lost this way.",
        )
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: GameState) -> None:
        controller = _get_controller(self)
        if controller is None:
            return
        x = self.x_value
        total_lost = 0
        for player in game.players:
            if player is not controller:
                player.life -= x
                total_lost += x
        controller.life += total_lost


__all__ = ["Exsanguinate"]
