"""Card implementation for Slumbering Trudge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SlumberingTrudge(Creature):
    """Slumbering Trudge."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Slumbering Trudge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}"))
        kwargs.setdefault("subtypes", {"Plant", "Beast"})
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        x_value = max(0, int(getattr(self, "x_value", 0)))
        stun_counters = max(0, 3 - x_value)
        if stun_counters > 0:
            self._counters["stun"] = self._counters.get("stun", 0) + stun_counters
        if x_value <= 2:
            self.is_tapped = True
