"""Card implementation for Tester of the Tangential."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class TesterOfTheTangential(Creature):
    """Tester of the Tangential — {1}{U} — 1/1 — Creature — Djinn Wizard.

    Increment (Whenever you cast a spell, if the amount of mana you spent
    is greater than this creature's power or toughness, put a +1/+1 counter
    on this creature.)

    At the beginning of combat on your turn, you may pay {X}. When you do,
    move X +1/+1 counters from this creature onto another target creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tester of the Tangential")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("keywords", Keyword.INCREMENT)
        kwargs.setdefault("subtypes", {"Djinn", "Wizard"})
        super().__init__(**kwargs)

    def on_increment_trigger(self, game: "GameState", mana_spent: int) -> None:
        """Increment: add +1/+1 counter if mana_spent > power or toughness."""
        if mana_spent > self.power or mana_spent > self.toughness:
            self.plus_one_counters += 1
            self._base_plus_one_counters = self.plus_one_counters

    def move_counters(self, game: "GameState", target: Any, x: int) -> None:
        """Move X +1/+1 counters from this creature to target."""
        if x <= 0:
            return
        # Can't move more than available
        actual = min(x, self.plus_one_counters)
        self.plus_one_counters -= actual
        self._base_plus_one_counters = self.plus_one_counters
        target.plus_one_counters += actual
        if hasattr(target, "_base_plus_one_counters"):
            target._base_plus_one_counters = target.plus_one_counters
