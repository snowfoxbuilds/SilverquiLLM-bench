"""Card implementation for Wild Hypothesis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class WildHypothesis(Sorcery):
    """Wild Hypothesis — {X}{G} — Sorcery.

    Create a 0/0 green and blue Fractal creature token. Put X +1/+1 counters on it.
    Surveil 2.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wild Hypothesis")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}"))
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Create Fractal token with X counters, then surveil 2."""
        from engine.game import create_token

        controller = self.controller or self.owner
        if controller is None:
            return

        # Create 0/0 green and blue Fractal creature token
        token = Creature(
            name="Fractal",
            subtypes={"Fractal"},
            base_power=0,
            base_toughness=0,
            owner=controller,
            controller=controller,
        )
        token.colors = {"G", "U"}
        create_token(game, controller, token)

        # Put X +1/+1 counters on it
        token.plus_one_counters = self.x_value

        # Surveil 2
        library = game.get_library(controller)
        graveyard = game.get_graveyard(controller)
        choices = getattr(controller, "surveil_choices", [])
        for i in range(2):
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[0]
            # If choice is True (or default), put in graveyard
            to_graveyard = choices[i] if i < len(choices) else False
            if to_graveyard:
                library.remove(card)
                graveyard.add(card)
            # Otherwise leave on top of library
