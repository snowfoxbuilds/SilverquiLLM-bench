"""Card implementation for Quick Study."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class QuickStudy(Instant):
    """Quick Study — {2}{U} — Instant.

    Draw two cards.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quick Study")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """No targets."""
        return []

    def on_resolve(self, game: "GameState") -> None:
        """Draw two cards."""
        from engine.game import draw_card
        controller = self.controller or self.owner
        draw_card(game, controller)
        draw_card(game, controller)
