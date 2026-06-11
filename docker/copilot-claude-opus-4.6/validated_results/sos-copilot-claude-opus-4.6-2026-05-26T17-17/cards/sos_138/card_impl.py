"""Card implementation for Aberrant Manawurm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class AberrantManawurm(Creature):
    """Aberrant Manawurm — {3}{G} — Creature — Wurm — 2/5.

    Trample
    Whenever you cast an instant or sorcery spell, this creature gets +X/+0
    until end of turn, where X is the amount of mana spent to cast that spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Aberrant Manawurm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("subtypes", {"Wurm"})
        kwargs.setdefault(
            "rules_text",
            "Trample\nWhenever you cast an instant or sorcery spell, this "
            "creature gets +X/+0 until end of turn, where X is the amount of "
            "mana spent to cast that spell.",
        )
        super().__init__(**kwargs)
        self._temp_power_bonus: int = 0

    def on_spell_cast(self, game: "GameState", spell: Any = None) -> None:
        """Trigger: +X/+0 when controller casts an instant or sorcery."""
        if spell is None:
            return
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        mana_spent = getattr(spell, "mana_spent", 0)
        self._temp_power_bonus = getattr(self, "_temp_power_bonus", 0) + mana_spent

    def end_turn_cleanup(self) -> None:
        """Reset temporary power bonus at end of turn."""
        self._temp_power_bonus = 0
