"""Card implementation for Sneering Shadewriter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SneeringShadewriter(Creature):
    """Sneering Shadewriter — {4}{B} — Creature — Vampire Warlock.

    3/3, Flying.
    When this creature enters, each opponent loses 2 life and you gain 2 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sneering Shadewriter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Each opponent loses 2 life and controller gains 2 life."""
        controller = self.controller
        for player in game.players:
            if player is not controller:
                player.life -= 2
        controller.life += 2
        if not hasattr(controller, "life_gained_this_turn"):
            controller.life_gained_this_turn = 0
        controller.life_gained_this_turn += 2
