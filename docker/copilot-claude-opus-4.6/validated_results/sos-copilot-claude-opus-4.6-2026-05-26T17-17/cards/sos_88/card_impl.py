"""Card implementation for Leech Collector // Bloodletting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LeechCollector(Creature):
    """{1}{B} Creature — Human Warlock 2/2.

    Whenever you gain life for the first time each turn, this creature becomes
    prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Leech Collector")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Human", "Warlock"})
        super().__init__(**kwargs)
        self.prepared: bool = False
        self._life_gained_this_turn: bool = False

    def on_life_gained(self, game: "GameState", player: Any, amount: int) -> None:
        """Trigger: first life gain each turn prepares this creature."""
        if player is not self.controller:
            return
        if self._life_gained_this_turn:
            return
        self._life_gained_this_turn = True
        self.prepared = True
