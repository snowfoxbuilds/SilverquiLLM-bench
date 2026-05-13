"""Card implementation for AntiquitiesOnTheLoose."""

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



class AntiquitiesOnTheLoose(Sorcery):
    """Antiquities on the Loose — {1}{W}{W} — Create two 2/2 red and white
    Spirit creature tokens.

    The flashback cost and +1/+1 counter bonus are not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Antiquities on the Loose")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create two 2/2 red and white Spirit creature tokens. Then if "
            "this spell was cast from anywhere other than your hand, put a "
            "+1/+1 counter on each Spirit you control.\n"
            "Flashback {4}{W}{W}",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        for _ in range(2):
            token = Creature(
                name="Spirit",
                base_power=2,
                base_toughness=2,
                subtypes={"Spirit"},
            )
            create_token(game, controller, token)


__all__ = ["AntiquitiesOnTheLoose"]
