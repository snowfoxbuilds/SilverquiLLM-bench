"""Card implementation for Scolding Administrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ScoldingAdministrator(Creature):
    """Scolding Administrator — {W}{B} — Creature — Dwarf Cleric, 2/2.

    Menace.
    Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, put a +1/+1 counter on this creature.
    When this creature dies, if it had counters on it, put those counters on
    up to one target creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scolding Administrator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Cleric"})
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("rules_text",
            "Menace\n"
            "Repartee — Whenever you cast an instant or sorcery spell that targets "
            "a creature, put a +1/+1 counter on this creature.\n"
            "When this creature dies, if it had counters on it, put those counters "
            "on up to one target creature.")
        super().__init__(**kwargs)

    def on_spell_cast_targeting_creature(self, game: "GameState", target: Any) -> None:
        """Repartee trigger: put a +1/+1 counter on this creature."""
        self.plus_one_counters += 1
        self._base_plus_one_counters = self.plus_one_counters

    def on_spell_cast_no_creature_target(self, game: "GameState") -> None:
        """No trigger for spells that don't target a creature."""
        pass

    def on_death(self, game: "GameState", chosen_target: Any = None) -> None:
        """When this creature dies, transfer counters to target creature."""
        if self.plus_one_counters <= 0:
            return
        if chosen_target is None:
            return
        chosen_target.plus_one_counters += self.plus_one_counters
        if hasattr(chosen_target, "_base_plus_one_counters"):
            chosen_target._base_plus_one_counters = chosen_target.plus_one_counters
