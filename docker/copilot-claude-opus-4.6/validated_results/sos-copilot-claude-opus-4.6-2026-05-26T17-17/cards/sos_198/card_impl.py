"""Card implementation for Kirol, History Buff // Pack a Punch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class KirolHistoryBuffPackAPunch(Creature):
    """Kirol, History Buff // Pack a Punch — {R}{W} — 2/3 Legendary Creature — Vampire Cleric.

    Whenever one or more cards leave your graveyard, Kirol becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kirol, History Buff")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("subtypes", {"Vampire", "Cleric"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.is_legendary: bool = True
        self.is_prepared: bool = False

    def on_card_leaves_graveyard(self, game: "GameState", player: Any, card: Any) -> None:
        """When one or more cards leave the controller's graveyard, become prepared."""
        if player is self.controller:
            self.is_prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Pack a Punch and unprepare."""
        if not self.is_prepared:
            return
        self.is_prepared = False
