"""Card implementation for Tackle Artist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class TackleArtist(Creature):
    """Tackle Artist — {3}{R} — Creature — Orc Sorcerer — 4/3.

    Trample
    Opus — Whenever you cast an instant or sorcery spell, put a +1/+1 counter
    on this creature. If five or more mana was spent to cast that spell, put
    two +1/+1 counters on this creature instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tackle Artist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.OPUS)
        kwargs.setdefault("subtypes", {"Orc", "Sorcerer"})
        kwargs.setdefault(
            "rules_text",
            "Trample\nOpus — Whenever you cast an instant or sorcery spell, "
            "put a +1/+1 counter on this creature. If five or more mana was "
            "spent to cast that spell, put two +1/+1 counters on this creature instead.",
        )
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", mana_spent: int = 0) -> None:
        """Opus trigger: add +1/+1 counters based on mana spent."""
        if mana_spent >= 5:
            self.plus_one_counters += 2
            self._base_plus_one_counters += 2
        else:
            self.plus_one_counters += 1
            self._base_plus_one_counters += 1

