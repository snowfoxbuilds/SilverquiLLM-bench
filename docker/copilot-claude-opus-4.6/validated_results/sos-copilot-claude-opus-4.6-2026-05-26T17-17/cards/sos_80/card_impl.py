"""Card implementation for Emeritus of Woe // Demonic Tutor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfWoe(Creature):
    """Emeritus of Woe — {3}{B} — 5/4 Creature — Vampire Warlock.

    This creature enters prepared. While prepared, you may cast a copy of
    Demonic Tutor (search library for a card, put it into your hand).
    Doing so unprepares it.
    At the beginning of your end step, if two or more creatures died this
    turn, this creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Woe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.PREPARED)
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
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
        """Cast Demonic Tutor: search library for a card, put it into hand."""
        if not self._prepared:
            return False
        if not targets:
            return False
        self._prepared = False
        target = targets[0]
        controller = self.controller
        library = game.get_library(controller)
        hand = game.get_hand(controller)
        if target in library.get_all():
            library.remove(target)
            hand.add(target)
        return True

    def end_step_trigger(self, game: "GameState") -> None:
        """At end step, if 2+ creatures died this turn, become prepared."""
        died = getattr(game, "creatures_died_this_turn", 0)
        if died >= 2:
            self._prepared = True
