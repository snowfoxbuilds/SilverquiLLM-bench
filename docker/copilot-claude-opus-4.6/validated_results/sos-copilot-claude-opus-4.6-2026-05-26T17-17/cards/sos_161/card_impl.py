"""Card implementation for Snarl Song."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Sorcery
from engine.game import create_token
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class FractalToken(Creature):
    """A 0/0 green and blue Fractal creature token."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.pop("colors", None)
        kwargs.setdefault("name", "Fractal")
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        kwargs.setdefault("subtypes", {"Fractal"})
        super().__init__(**kwargs)
        self.colors = ["G", "U"]


class SnarlSong(Sorcery):
    """Snarl Song — {5}{G} — Sorcery.

    Converge — Create two 0/0 green and blue Fractal creature tokens.
    Put X +1/+1 counters on each of them and you gain X life,
    where X is the number of colors of mana spent to cast this spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Snarl Song")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}"))
        super().__init__(**kwargs)
        self.colors_of_mana_spent: int = 0

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller
        x = self.colors_of_mana_spent

        # Create two Fractal tokens
        for _ in range(2):
            token = FractalToken(owner=controller, controller=controller)
            token.is_token = True
            token.plus_one_counters = x
            battlefield = game.get_battlefield(controller)
            battlefield.add(token)

        # Gain X life
        controller.life += x
