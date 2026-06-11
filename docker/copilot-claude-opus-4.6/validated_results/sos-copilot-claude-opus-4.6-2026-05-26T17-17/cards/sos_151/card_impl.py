"""Card implementation for Hungry Graffalon."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class HungryGraffalon(Creature):
    """Hungry Graffalon — {3}{G} — Creature — Giraffe (3/4).

    Reach
    Increment — Whenever you cast a spell, if the amount of mana you spent
    is greater than this creature's power or toughness, put a +1/+1 counter
    on this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hungry Graffalon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("subtypes", {"Giraffe"})
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", mana_spent: int = 0) -> None:
        """Increment trigger: add a +1/+1 counter if mana spent > power or toughness."""
        if mana_spent > self.power or mana_spent > self.toughness:
            self.plus_one_counters += 1
            self._base_plus_one_counters += 1
