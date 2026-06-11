"""Card implementation for Wildgrowth Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class WildgrowthArchaic(Creature):
    """Wildgrowth Archaic — {2/G}{2/G} — Creature — Avatar — 0/0.

    Trample, reach.
    Converge — Enters with a +1/+1 counter for each color of mana spent to cast it.
    Whenever you cast a creature spell, that creature enters with X additional
    +1/+1 counters where X is colors of mana spent to cast it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wildgrowth Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2/G}{2/G}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.REACH)
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        super().__init__(**kwargs)
        self.colors_of_mana_spent: set[str] = set()

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Converge — enters with +1/+1 counters equal to colors of mana spent."""
        self.plus_one_counters = len(self.colors_of_mana_spent)

    def on_creature_cast(self, game: "GameState", creature: Any) -> None:
        """Whenever you cast a creature spell, grant additional counters on enter."""
        colors = getattr(creature, "colors_of_mana_spent", set())
        count = len(colors)
        creature.additional_counters_on_enter = count
