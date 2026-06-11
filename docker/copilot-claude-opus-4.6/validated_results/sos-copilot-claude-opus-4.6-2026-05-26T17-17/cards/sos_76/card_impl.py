"""Card implementation for Cheerful Osteomancer // Raise Dead."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class CheerfulOsteomancer(Creature):
    """Cheerful Osteomancer — {3}{B} — 4/2 Creature — Orc Warlock.

    This creature enters prepared. While prepared, you may cast a copy of
    Raise Dead (return target creature card from your graveyard to your hand).
    Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cheerful Osteomancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.PREPARED)
        kwargs.setdefault("subtypes", {"Orc", "Warlock"})
        super().__init__(**kwargs)
        self._prepared: bool = False

    @property
    def prepared(self) -> bool:
        return self._prepared

    @prepared.setter
    def prepared(self, value: bool) -> None:
        self._prepared = value

    def on_resolve(self, game: "GameState") -> None:
        """Enters prepared."""
        self._prepared = True

    def cast_prepared_spell(self, game: "GameState", targets: list[Any] | None = None) -> bool | None:
        """Cast Raise Dead: return target creature from graveyard to hand."""
        if not self._prepared:
            return False
        if not targets:
            return False
        self._prepared = False
        target = targets[0]
        controller = self.controller
        graveyard = game.get_graveyard(controller)
        hand = game.get_hand(controller)
        if target in graveyard.get_all():
            graveyard.remove(target)
            hand.add(target)
        return True
