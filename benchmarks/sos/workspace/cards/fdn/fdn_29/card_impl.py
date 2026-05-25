"""Card implementation for Arcane Epiphany."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ArcaneEpiphany(Instant):
    """Arcane Epiphany — {3}{U}{U} — Instant.

    This spell costs {1} less to cast if you control a Wizard.
    Draw three cards.

    FDN collector number 29.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arcane Epiphany")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast if you control a Wizard.\n"
            "Draw three cards.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce cost by {1} if you control a Wizard."""
        controller = self.controller
        if controller is None:
            return 0
        battlefield = game.get_battlefield(controller)
        for obj in battlefield.get_all():
            if "Wizard" in getattr(obj, "subtypes", set()):
                return 1
        return 0

    def on_resolve(self, game: "GameState") -> None:
        """Draw three cards."""
        from benchmarks.sos.workspace.engine.game import draw_card

        controller = self.controller
        if controller is None:
            return
        for _ in range(3):
            draw_card(game, controller)
