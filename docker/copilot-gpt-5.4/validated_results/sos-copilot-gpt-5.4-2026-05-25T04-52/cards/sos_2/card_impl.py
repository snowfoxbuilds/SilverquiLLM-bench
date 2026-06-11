"""Card implementation for Rancorous Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RancorousArchaic(Creature):
    """Rancorous Archaic."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rancorous Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.REACH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Trample, reach\nConverge — This creature enters with a +1/+1 counter "
            "on it for each color of mana spent to cast it.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        colors_spent = set(getattr(self, "colors_spent", []))
        counters = len(colors_spent)
        self.plus_one_counters += counters
        self._base_plus_one_counters = self.plus_one_counters
