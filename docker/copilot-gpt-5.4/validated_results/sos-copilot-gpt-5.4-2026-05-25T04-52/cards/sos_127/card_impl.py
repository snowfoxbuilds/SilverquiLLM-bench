"""Card implementation for Rearing Embermare."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RearingEmbermare(Creature):
    """Rearing Embermare."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rearing Embermare")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("subtypes", {"Horse", "Beast"})
        kwargs.setdefault("keywords", Keyword.REACH | Keyword.HASTE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)
