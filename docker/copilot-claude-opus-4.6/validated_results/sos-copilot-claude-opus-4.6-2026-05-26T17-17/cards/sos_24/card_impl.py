"""Card implementation for Owlin Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class OwlinHistorian(Creature):
    """Owlin Historian — {2}{W} — 2/3 Bird Cleric.

    Flying.
    When this creature enters, surveil 1.
    Whenever one or more cards leave your graveyard, this creature gets
    +1/+1 until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Owlin Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Bird", "Cleric"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self._graveyard_leave_bonus: int = 0

    def get_power(self, game: "GameState") -> int:
        """Return current power including graveyard-leave bonus."""
        return self.power + self._graveyard_leave_bonus

    def get_toughness(self, game: "GameState") -> int:
        """Return current toughness including graveyard-leave bonus."""
        return self.toughness + self._graveyard_leave_bonus

    def on_enter_battlefield(self, game: "GameState", surveil_choice: str = "top") -> None:
        """ETB: surveil 1 — look at top card, optionally put it into graveyard."""
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        cards = library.get_all()
        if not cards:
            return

        top_card = cards[-1]  # top of library is last element

        if surveil_choice == "graveyard":
            library.remove(top_card)
            game.get_graveyard(controller).add(top_card)
        # else "top" — leave it on top, do nothing

    def on_cards_leave_graveyard(self, game: "GameState") -> None:
        """Trigger: one or more cards left graveyard, +1/+1 until end of turn."""
        self._graveyard_leave_bonus += 1
