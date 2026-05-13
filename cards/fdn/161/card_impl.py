"""Card implementation for SnarlSong."""

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



class SnarlSong(Sorcery):
    """Snarl Song — {5}{G} — Converge — Create two 0/0 green and blue Fractal
    creature tokens. Put X +1/+1 counters on each and gain X life, where X
    is the number of colors of mana spent to cast this spell.

    Simplified: assumes 1 color of mana was spent (green). Creates two
    0/0 Fractal tokens with 1 +1/+1 counter each and gains 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Snarl Song")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Create two 0/0 green and blue Fractal creature "
            "tokens. Put X +1/+1 counters on each of them and you gain X "
            "life, where X is the number of colors of mana spent to cast "
            "this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Converge count: check how many colors were spent
        colors_spent_raw = getattr(self, "colors_spent", 1)
        # colors_spent may be a list of Color enums or an integer
        if isinstance(colors_spent_raw, (list, set)):
            colors_spent = len(colors_spent_raw)
        else:
            colors_spent = int(colors_spent_raw)

        for _ in range(2):
            token = Creature(
                name="Fractal",
                base_power=0,
                base_toughness=0,
                subtypes={"Fractal"},
            )
            token.plus_one_counters = colors_spent
            create_token(game, controller, token)

        # Gain life equal to colors spent
        controller.life += colors_spent


__all__ = ["SnarlSong"]
