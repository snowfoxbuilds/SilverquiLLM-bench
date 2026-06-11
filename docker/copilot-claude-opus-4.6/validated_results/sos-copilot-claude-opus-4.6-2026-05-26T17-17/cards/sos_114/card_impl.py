"""Card implementation for Expressive Firedancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ExpressiveFiredancer(Creature):
    """Expressive Firedancer — {1}{R} — Creature — Human Sorcerer.

    Opus — Whenever you cast an instant or sorcery spell, this creature gets
    +1/+1 until end of turn. If five or more mana was spent to cast that spell,
    this creature also gains double strike until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Expressive Firedancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Sorcerer"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Opus — Whenever you cast an instant or sorcery spell, this creature "
            "gets +1/+1 until end of turn. If five or more mana was spent to cast "
            "that spell, this creature also gains double strike until end of turn.",
        )
        super().__init__(**kwargs)
        self._temp_power_bonus: int = 0
        self._temp_toughness_bonus: int = 0
        self._has_temp_double_strike: bool = False

    def on_instant_or_sorcery_cast(self, game: "GameState", spell: Any) -> None:
        """Trigger: +1/+1 until end of turn; double strike if 5+ mana spent."""
        self._temp_power_bonus += 1
        self._temp_toughness_bonus += 1

        mana_spent = getattr(spell, "mana_spent", 0)
        if mana_spent >= 5:
            self._has_temp_double_strike = True
            self.keywords = self.keywords | Keyword.DOUBLE_STRIKE

    def end_of_turn_cleanup(self, game: "GameState") -> None:
        """Remove temporary bonuses at end of turn."""
        self._temp_power_bonus = 0
        self._temp_toughness_bonus = 0
        if self._has_temp_double_strike:
            self._has_temp_double_strike = False
            # Remove double strike - reset to original keywords
            self.keywords = self._original_keywords
