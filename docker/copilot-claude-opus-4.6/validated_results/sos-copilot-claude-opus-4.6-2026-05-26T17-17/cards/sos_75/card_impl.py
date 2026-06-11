"""Card implementation for Burrog Banemaker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class BurrogBanemaker(Creature):
    """Burrog Banemaker — {B} — Creature — Frog Warlock.

    Deathtouch
    {1}{B}: This creature gets +1/+1 until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burrog Banemaker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("subtypes", {"Frog", "Warlock"})
        super().__init__(**kwargs)
        self._temp_power_bonus: int = 0
        self._temp_toughness_bonus: int = 0

        self.activated_abilities: list[ActivatedAbility] = [
            ActivatedAbility(
                cost=lambda game: None,
                effect=self._pump_effect,
                description="{1}{B}: This creature gets +1/+1 until end of turn.",
            )
        ]

    def _pump_effect(self, game: "GameState") -> None:
        """Grant +1/+1 until end of turn."""
        self._temp_power_bonus += 1
        self._temp_toughness_bonus += 1

    @property
    def power(self) -> int:
        """Current power including counter modifications and temp bonuses."""
        base = self.modified_power + self.plus_one_counters - self.minus_one_counters
        return base + self._temp_power_bonus

    @property
    def toughness(self) -> int:
        """Current toughness including counter modifications and temp bonuses."""
        base = self.modified_toughness + self.plus_one_counters - self.minus_one_counters
        return base + self._temp_toughness_bonus

    def end_of_turn_cleanup(self, game: "GameState") -> None:
        """Reset temporary bonuses at end of turn."""
        self._temp_power_bonus = 0
        self._temp_toughness_bonus = 0
