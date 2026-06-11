"""Card implementation for Pensive Professor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PensiveProfessor(Creature):
    """Pensive Professor — {1}{U}{U} — Creature — Human Wizard.

    Increment (Whenever you cast a spell, if the amount of mana you spent is
    greater than this creature's power or toughness, put a +1/+1 counter on it.)
    Whenever one or more +1/+1 counters are put on this creature, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pensive Professor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.INCREMENT)
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", mana_spent: int = 0) -> None:
        """Increment: if mana spent > power or toughness, add a +1/+1 counter."""
        current_power = self.power
        current_toughness = self.toughness
        if mana_spent > current_power or mana_spent > current_toughness:
            self.add_plus_one_counter(game, 1)

    def add_plus_one_counter(self, game: "GameState", amount: int = 1) -> None:
        """Add +1/+1 counters and trigger draw (once per batch)."""
        if amount <= 0:
            return
        self.plus_one_counters += amount
        # Sync base counters
        if hasattr(self, "_base_plus_one_counters"):
            self._base_plus_one_counters = self.plus_one_counters
        # Trigger: draw a card (once per batch of counters)
        from engine.game import draw_card
        controller = self.controller or self.owner
        draw_card(game, controller)
