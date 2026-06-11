"""Card implementation for Slumbering Trudge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SlumberingTrudge(Creature):
    """Slumbering Trudge — {X}{G} — 6/6 Creature — Plant Beast.

    This creature enters with a number of stun counters on it equal to
    three minus X. If X is 2 or less, it enters tapped.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Slumbering Trudge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}"))
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault("subtypes", {"Plant", "Beast"})
        super().__init__(**kwargs)
        self.x_value: int = 0
        self.stun_counters: int = 0

    def on_enter_battlefield(self, game: "GameState") -> None:
        """Enter with stun counters and possibly tapped."""
        x = getattr(self, "x_value", 0)
        stun = max(0, 3 - x)
        self.stun_counters = stun
        if x <= 2:
            self.is_tapped = True
