"""Card implementation for Fractal Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class FractalMascot(Creature):
    """Fractal Mascot — {4}{G}{U} — Creature — Fractal Elk (6/6).

    Trample
    When this creature enters, tap target creature an opponent controls.
    Put a stun counter on it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{U}"))
        kwargs.setdefault("subtypes", {"Fractal", "Elk"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def on_enter_battlefield(self, game: "GameState") -> None:
        """ETB: tap target creature an opponent controls and put a stun counter on it."""
        if not self.chosen_targets:
            return

        target = self.chosen_targets[0]
        target.tapped = True

        # Put a stun counter on target
        stun = getattr(target, "stun_counters", 0)
        target.stun_counters = stun + 1
