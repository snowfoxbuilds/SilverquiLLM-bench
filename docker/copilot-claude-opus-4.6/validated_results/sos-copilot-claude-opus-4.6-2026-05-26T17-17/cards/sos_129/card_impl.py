"""Card implementation for Seize the Spoils."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery, CardImpl
from engine.game import draw_card, create_token
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class TreasureToken(CardImpl):
    """A Treasure artifact token."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Treasure")
        kwargs.setdefault("card_types", {CardType.ARTIFACT})
        kwargs.setdefault("subtypes", {"Treasure"})
        super().__init__(**kwargs)
        self.is_treasure: bool = True
        self.is_token: bool = True


class SeizeTheSpoils(Sorcery):
    """Seize the Spoils — {2}{R} — Sorcery.

    Additional cost: discard a card.
    Draw two cards and create a Treasure token.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Seize the Spoils")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)

    def get_additional_costs(self) -> list[dict[str, Any]]:
        """Return additional costs required to cast this spell."""
        return [{"type": "discard", "count": 1}]

    def on_resolve(self, game: "GameState") -> None:
        """Draw 2 cards and create a Treasure token."""
        player = self.controller
        # Draw 2 cards
        draw_card(game, player)
        draw_card(game, player)
        # Create a Treasure token
        token = TreasureToken(owner=player, controller=player)
        create_token(game, player, token)
