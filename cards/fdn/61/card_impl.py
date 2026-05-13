"""Card implementation for MusesEncouragement."""

from __future__ import annotations


from engine.card import Artifact, Creature, Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any
import math

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class MusesEncouragement(Instant):
    """Muse's Encouragement — {4}{U} — Create a 3/3 blue and red Elemental
    creature token with flying. Surveil 2.

    Surveil 2 is simplified: top 2 cards go to graveyard.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muse's Encouragement")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 3/3 blue and red Elemental creature token with flying.\n"
            "Surveil 2.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Create 3/3 Elemental with flying
        token = Creature(
            name="Elemental",
            base_power=3,
            base_toughness=3,
            subtypes={"Elemental"},
            keywords=Keyword.FLYING,
        )
        create_token(game, controller, token)

        # Surveil 2 — look at top 2, put into graveyard
        library = controller.zones[Zone.LIBRARY]
        graveyard = controller.zones[Zone.GRAVEYARD]
        to_surveil = min(2, len(library))
        for _ in range(to_surveil):
            cards = library.top(1)
            if cards:
                card = cards[0]
                library.remove(card)
                graveyard.add(card)


__all__ = ["MusesEncouragement"]
