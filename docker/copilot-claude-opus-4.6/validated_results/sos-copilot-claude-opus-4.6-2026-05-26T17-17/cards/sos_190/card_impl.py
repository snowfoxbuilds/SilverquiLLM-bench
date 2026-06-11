"""Card implementation for Fractal Tender."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class FractalTender(Creature):
    """Fractal Tender — {3}{G}{U} — Creature — Elf Wizard (3/3).

    Ward {2}
    Increment (Whenever you cast a spell, if the amount of mana you spent
    is greater than this creature's power or toughness, put a +1/+1 counter
    on this creature.)
    At the beginning of each end step, if you put a counter on this creature
    this turn, create a 0/0 green and blue Fractal creature token and put
    three +1/+1 counters on it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Tender")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{U}"))
        kwargs.setdefault("subtypes", {"Elf", "Wizard"})
        kwargs.setdefault("keywords", Keyword.WARD | Keyword.INCREMENT)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.counter_placed_this_turn: bool = False

    def on_spell_cast(self, game: "GameState", mana_spent: int = 0) -> None:
        """Increment: if mana spent > power or toughness, add +1/+1 counter."""
        power = self.base_power + self.plus_one_counters - self.minus_one_counters
        toughness = self.base_toughness + self.plus_one_counters - self.minus_one_counters

        if mana_spent > power or mana_spent > toughness:
            self.plus_one_counters += 1
            self._base_plus_one_counters += 1
            self.counter_placed_this_turn = True

    def on_end_step(self, game: "GameState") -> None:
        """If a counter was placed this turn, create a 0/0 Fractal with 3 +1/+1 counters."""
        from engine.game import create_token

        if not self.counter_placed_this_turn:
            return

        controller = self.controller
        if controller is None:
            return

        token = Creature(
            name="Fractal",
            subtypes={"Fractal"},
            base_power=0,
            base_toughness=0,
        )
        token.plus_one_counters = 3
        token._base_plus_one_counters = 3
        create_token(game, controller, token)
