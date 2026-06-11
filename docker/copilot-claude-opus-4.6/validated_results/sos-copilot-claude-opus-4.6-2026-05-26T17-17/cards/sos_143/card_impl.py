"""Card implementation for Comforting Counsel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Enchantment, Creature
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ComfortingCounsel(Enchantment):
    """Comforting Counsel — {1}{G} — Enchantment.

    Whenever you gain life, put a growth counter on this enchantment.
    As long as there are five or more growth counters on this enchantment,
    creatures you control get +3/+3.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Comforting Counsel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)
        self.growth_counters: int = 0

    def on_life_gained(self, game: "GameState", player: Any, amount: int) -> None:
        """Triggered ability: put a growth counter when controller gains life."""
        if player is self.controller:
            self.growth_counters += 1

    def apply_continuous_effect(self, game: "GameState") -> None:
        """Static ability: if 5+ growth counters, creatures you control get +3/+3."""
        if self.growth_counters < 5:
            return
        controller = self.controller
        if controller is None:
            return
        bf = game.get_battlefield(controller)
        for obj in bf.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                obj._temp_power_bonus = getattr(obj, "_temp_power_bonus", 0) + 3
                obj._temp_toughness_bonus = getattr(obj, "_temp_toughness_bonus", 0) + 3
