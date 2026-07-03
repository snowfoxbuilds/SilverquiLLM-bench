"""Card implementation for Muse's Encouragement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MusesEncouragement(Instant):
    """Muse's Encouragement — {4}{U} — Instant.

    Create a 3/3 blue and red Elemental creature token with flying.
    Surveil 2.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muse's Encouragement")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner
        # Create 3/3 blue/red Elemental token with flying
        token = Creature(
            name="Elemental",
            owner=controller,
            controller=controller,
            base_power=3,
            base_toughness=3,
            keywords=Keyword.FLYING,
            subtypes={"Elemental"},
        )
        token.colors = ["U", "R"]
        token.is_token = True
        game.get_battlefield(controller).add(token)

        # Surveil 2
        library = game.get_library(controller)
        graveyard = game.get_graveyard(controller)
        n = min(2, len(library))
        if n > 0:
            top_cards = library.top(n)
            # Default surveil: put all into graveyard
            for card in top_cards:
                library.remove(card)
                graveyard.add(card)
