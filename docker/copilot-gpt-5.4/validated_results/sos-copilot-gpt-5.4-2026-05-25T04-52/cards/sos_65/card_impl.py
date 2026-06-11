"""Card implementation for Quick Study."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class QuickStudy(Instant):
    """Quick Study."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quick Study")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("rules_text", "Draw two cards.")
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        draw_card(game, controller)
        draw_card(game, controller)
