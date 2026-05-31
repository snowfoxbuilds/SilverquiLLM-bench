"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from engine.card import CardImpl


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def granted_casualty_value(
        self,
        game: "GameState",
        spell: "CardImpl",
        caster: "Player",
    ) -> int:
        """Grant casualty 1 to your instant and sorcery spells."""
        if self.controller is not caster:
            return 0
        if not getattr(game.get_battlefield(caster), "contains")(self):
            return 0
        if not getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}:
            return 0
        return 1
