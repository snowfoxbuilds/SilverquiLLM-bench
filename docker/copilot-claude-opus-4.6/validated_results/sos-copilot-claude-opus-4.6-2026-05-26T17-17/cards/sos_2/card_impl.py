"""Card implementation for Rancorous Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class RancorousArchaic(Creature):
    """Rancorous Archaic — {5} — Creature — Avatar — 2/2.

    Trample, reach
    Converge — This creature enters with a +1/+1 counter on it for each
    color of mana spent to cast it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rancorous Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.REACH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Trample, reach\nConverge — This creature enters with a +1/+1 "
            "counter on it for each color of mana spent to cast it.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: add +1/+1 counters equal to number of colors of mana spent."""
        from engine.game import add_counter

        colors_spent = getattr(self, "colors_spent", None)
        if colors_spent is None:
            return
        # colors_spent is a list of Color enum values from the casting pipeline
        if isinstance(colors_spent, (list, tuple)):
            count = len(set(colors_spent))
        else:
            count = int(colors_spent)
        if count > 0:
            add_counter(game, self, "+1/+1", count)
            # Sync base counters so _reset_characteristics preserves them
            self._base_plus_one_counters = self.plus_one_counters
