"""Card implementation for Joined Researchers // Secret Rendezvous."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class JoinedResearchersSecretRendezvous(Creature):
    """Joined Researchers // Secret Rendezvous — {1}{W} — 2/2 Human Cleric Wizard.

    First strike.
    At the beginning of each end step, if an opponent has more cards in hand
    than you, this creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Joined Researchers // Secret Rendezvous")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_end_step(self, game: "GameState") -> None:
        """At the beginning of each end step, check if opponent has more cards."""
        controller = self.controller
        if controller is None:
            return

        controller_hand_size = len(game.get_hand(controller).get_all())

        for player in game.players:
            if player is not controller:
                if len(game.get_hand(player).get_all()) > controller_hand_size:
                    self.is_prepared = True
                    return
