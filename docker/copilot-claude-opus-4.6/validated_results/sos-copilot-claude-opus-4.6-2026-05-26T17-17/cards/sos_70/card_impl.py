"""Card implementation for Textbook Tabulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class TextbookTabulator(Creature):
    """Textbook Tabulator — {2}{U} — 0/3 — Creature — Frog Wizard.

    Increment (Whenever you cast a spell, if the amount of mana you spent
    is greater than this creature's power or toughness, put a +1/+1 counter
    on this creature.)

    When this creature enters, surveil 2.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Textbook Tabulator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("keywords", Keyword.INCREMENT | Keyword.SURVEIL)
        kwargs.setdefault("subtypes", {"Frog", "Wizard"})
        super().__init__(**kwargs)

    def on_increment_trigger(self, game: "GameState", mana_spent: int) -> None:
        """Increment: add +1/+1 counter if mana_spent > power or toughness."""
        if mana_spent > self.power or mana_spent > self.toughness:
            self.plus_one_counters += 1
            self._base_plus_one_counters = self.plus_one_counters

    def on_resolve(self, game: "GameState") -> None:
        """ETB: surveil 2."""
        controller = self.controller
        if controller is None:
            return
        self._surveil(game, controller, 2)

    def _surveil(self, game: "GameState", player: Any, n: int) -> None:
        """Surveil n: look at top n cards, put any into graveyard, rest on top."""
        library = game.get_library(player)
        graveyard = game.get_graveyard(player)

        cards = []
        all_cards = library.get_all()
        # Take up to n cards from top of library
        for i in range(min(n, len(all_cards))):
            cards.append(all_cards[-(i + 1)])  # top of library is end of list

        if not cards:
            return

        # Default behavior: put all into graveyard (simplification)
        for card in cards:
            library.remove(card)
            graveyard.add(card)
