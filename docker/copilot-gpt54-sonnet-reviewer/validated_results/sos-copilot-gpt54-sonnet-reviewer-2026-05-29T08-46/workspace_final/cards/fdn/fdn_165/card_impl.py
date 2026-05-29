"""Card implementation for Think Twice."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ThinkTwice(Instant):
    """Think Twice — {1}{U} — Instant.

    Draw a card.
    Flashback {2}{U}

    FDN collector number 165.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Think Twice")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Draw a card.\nFlashback {2}{U}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{2}{U}")

    def on_resolve(self, game: "GameState") -> None:
        """Draw a card."""
        from engine.game import draw_card

        controller = self.controller
        if controller is None:
            return
        draw_card(game, controller)
