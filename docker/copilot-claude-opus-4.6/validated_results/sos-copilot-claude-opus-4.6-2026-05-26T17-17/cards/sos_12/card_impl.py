"""Card implementation for Elite Interceptor // Rejoinder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EliteInterceptorRejoinder(Creature):
    """Elite Interceptor // Rejoinder — {W} — 1/2 — Human Wizard.

    This creature enters prepared. While prepared, you may cast a copy
    of its spell (Rejoinder, {1}{W} sorcery). Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elite Interceptor // Rejoinder")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """ETB: enters prepared."""
        self.is_prepared = True

    def can_cast_prepared(self, game: "GameState") -> bool:
        """Return True if the prepared spell can be cast."""
        return self.is_prepared

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Rejoinder and unprepare."""
        if not self.is_prepared:
            return
        self.is_prepared = False
