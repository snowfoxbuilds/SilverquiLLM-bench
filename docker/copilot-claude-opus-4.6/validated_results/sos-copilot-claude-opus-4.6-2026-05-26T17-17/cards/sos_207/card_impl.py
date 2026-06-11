"""Card implementation for Old-Growth Educator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class OldGrowthEducator(Creature):
    """Old-Growth Educator — {2}{B}{G} — 4/4 — Creature — Treefolk Druid.

    Vigilance, reach
    Infusion — When this creature enters, put two +1/+1 counters on it if you gained life this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Old-Growth Educator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{G}"))
        kwargs.setdefault("subtypes", {"Treefolk", "Druid"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE | Keyword.REACH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_enter_battlefield(self, game: "GameState", **kwargs: Any) -> None:
        """Infusion — put two +1/+1 counters if controller gained life this turn."""
        controller = self.controller
        if controller is not None and getattr(controller, 'life_gained_this_turn', 0) > 0:
            self.plus_one_counters += 2
