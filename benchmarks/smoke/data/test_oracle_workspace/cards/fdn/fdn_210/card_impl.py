"""Card implementation for Thrill of Possibility."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ThrillOfPossibility(Instant):
    """Thrill of Possibility — {1}{R} — Instant.

    As an additional cost to cast this spell, discard a card.
    Draw two cards.

    FDN collector number 210.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thrill of Possibility")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "As an additional cost to cast this spell, discard a card.\n"
            "Draw two cards.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Draw two cards (discard cost paid during casting)."""
        from engine.game import draw_card

        controller = self.controller
        if controller is None:
            return
        # ENGINE LIMITATION: additional cost (discard) is assumed paid
        # during casting pipeline. On resolve, just draw 2.
        draw_card(game, controller)
        draw_card(game, controller)
