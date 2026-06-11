"""Card implementation for Pterafractyl."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class Pterafractyl(Creature):
    """Pterafractyl — {X}{G}{U} — Creature — Dinosaur Fractal.

    1/0, Flying.
    This creature enters with X +1/+1 counters on it.
    When this creature enters, you gain 2 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pterafractyl")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}{U}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 0)
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("subtypes", {"Dinosaur", "Fractal"})
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Enter with X +1/+1 counters and gain 2 life."""
        self.plus_one_counters = self.x_value
        controller = self.controller or self.owner
        controller.gain_life(game, 2)
