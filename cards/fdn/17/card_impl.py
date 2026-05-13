"""Card implementation for GroupProject."""

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



class GroupProject(Sorcery):
    """Group Project — {1}{W} — Create a 2/2 red and white Spirit token.

    Flashback is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Group Project")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 2/2 red and white Spirit creature token.\n"
            "Flashback—Tap three untapped creatures you control.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        token = Creature(
            name="Spirit",
            base_power=2,
            base_toughness=2,
            subtypes={"Spirit"},
        )
        create_token(game, controller, token)


__all__ = ["GroupProject"]
