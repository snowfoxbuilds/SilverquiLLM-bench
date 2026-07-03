"""Card implementation for Stadium Tidalmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class StadiumTidalmage(Creature):
    """Stadium Tidalmage — {2}{U}{R} — Creature — Djinn Sorcerer — 4/4.

    Whenever this creature enters or attacks, you may draw a card.
    If you do, discard a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stadium Tidalmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{R}"))
        kwargs.setdefault("subtypes", {"Djinn", "Sorcerer"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def _loot(self, game: "GameState") -> None:
        """Draw a card, then discard a card (loot)."""
        from engine.game import draw_card, discard

        controller = self.controller
        drawn = draw_card(game, controller)
        if drawn is not None:
            # Discard a card - pick the last card in hand
            hand = game.get_hand(controller)
            cards = hand.get_all()
            if cards:
                discard(game, controller, cards[-1])

    def on_enter(self, game: "GameState") -> None:
        self._loot(game)

    def on_attack(self, game: "GameState") -> None:
        self._loot(game)
