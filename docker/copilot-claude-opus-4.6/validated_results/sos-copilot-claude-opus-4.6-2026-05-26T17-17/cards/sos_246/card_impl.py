"""Card implementation for Zaffai and the Tempests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class ZaffaiAndTheTempests(Creature):
    """Zaffai and the Tempests — {5}{U}{R} — 5/7 Legendary Creature — Human Bard Sorcerer.

    Once during each of your turns, you may cast an instant or sorcery spell
    from your hand without paying its mana cost.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zaffai and the Tempests")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{U}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Bard", "Sorcerer"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 7)
        super().__init__(**kwargs)
        self.legendary = True
        self.free_cast_used: bool = False

    def on_turn_start(self, game: "GameState") -> None:
        """Reset free cast permission at start of turn."""
        self.free_cast_used = False

    def modify_cast_cost(self, game: "GameState", spell: Any) -> ManaCost | None:
        """Allow one free instant/sorcery cast per turn."""
        if self.free_cast_used:
            return None
        from engine.types import CardType
        spell_types = getattr(spell, "card_types", set())
        if CardType.INSTANT in spell_types or CardType.SORCERY in spell_types:
            self.free_cast_used = True
            return ManaCost.parse("{0}")
        return None
