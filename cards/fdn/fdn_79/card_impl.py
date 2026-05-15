"""Card implementation for Boltwave."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class Boltwave(Sorcery):
    """Boltwave — {R} — Sorcery.

    Boltwave deals 3 damage to each opponent.

    FDN collector number 79.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Boltwave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault(
            "rules_text",
            "Boltwave deals 3 damage to each opponent.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Deal 3 damage to each opponent."""
        from engine.game import deal_damage

        controller = self.controller
        if controller is None:
            return
        for player in game.players:
            if player is not controller:
                deal_damage(game, self, player, 3)
