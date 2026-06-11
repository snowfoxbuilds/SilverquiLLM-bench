"""Card implementation for Send in the Pest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SendInThePest(Sorcery):
    """{1}{B} Sorcery — Each opponent discards a card. You create a 1/1
    black and green Pest creature token with "Whenever this token attacks,
    you gain 1 life."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Send in the Pest")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import create_token, discard

        controller = self.controller
        if controller is None:
            return

        # Each opponent discards a card
        for player in game.players:
            if player is not controller:
                hand = game.get_hand(player)
                cards = hand.get_all()
                if cards:
                    discard(game, player, cards[0])

        # Create a 1/1 Pest token
        pest = Creature(
            name="Pest",
            base_power=1,
            base_toughness=1,
            subtypes={"Pest"},
        )
        create_token(game, controller, pest)
