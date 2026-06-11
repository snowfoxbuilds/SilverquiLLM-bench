"""Card implementation for Mindful Biomancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class MindfulBiomancer(Creature):
    """Mindful Biomancer — {1}{G} — Creature — Dryad Druid (2/2).

    When this creature enters, you gain 1 life.
    {2}{G}: This creature gets +2/+2 until end of turn. Activate only once each turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mindful Biomancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Dryad", "Druid"})
        super().__init__(**kwargs)
        self._ability_activated_this_turn: bool = False

    def on_enter_battlefield(self, game: "GameState") -> None:
        """ETB: You gain 1 life."""
        controller = self.controller
        controller.life += 1

    def can_activate_ability(self, game: "GameState", index: int = 0) -> bool:
        """Check if ability can be activated (once per turn, needs mana)."""
        if self._ability_activated_this_turn:
            return False
        return True

    def activate_ability(self, game: "GameState", index: int = 0) -> None:
        """{2}{G}: This creature gets +2/+2 until end of turn."""
        self.modified_power += 2
        self.modified_toughness += 2
        self._ability_activated_this_turn = True

    def on_new_turn(self, game: "GameState") -> None:
        """Reset once-per-turn ability tracker."""
        self._ability_activated_this_turn = False
