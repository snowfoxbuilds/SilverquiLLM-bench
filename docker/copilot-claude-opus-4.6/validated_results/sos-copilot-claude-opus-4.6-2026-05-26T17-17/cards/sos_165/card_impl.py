"""Card implementation for Topiary Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class TopiaryLecturer(Creature):
    """Topiary Lecturer — {2}{G} — 1/2 — Elf Druid.

    Increment (Whenever you cast a spell, if the amount of mana you spent is
    greater than this creature's power or toughness, put a +1/+1 counter on
    this creature.)
    {T}: Add an amount of {G} equal to this creature's power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Topiary Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", mana_spent: int) -> None:
        """Increment: if mana spent > power or toughness, add a +1/+1 counter."""
        current_power = self.get_power(game)
        current_toughness = self.get_toughness(game)
        if mana_spent > current_power or mana_spent > current_toughness:
            self.plus_one_counters += 1

    def can_activate_mana_ability(self, game: "GameState") -> bool:
        """Check if the mana ability can be activated (must be untapped)."""
        return not self.is_tapped

    def activate_mana_ability(self, game: "GameState") -> dict:
        """Tap: Add {G} equal to this creature's power."""
        self.is_tapped = True
        power = self.get_power(game)
        return {ManaType.GREEN: power}
