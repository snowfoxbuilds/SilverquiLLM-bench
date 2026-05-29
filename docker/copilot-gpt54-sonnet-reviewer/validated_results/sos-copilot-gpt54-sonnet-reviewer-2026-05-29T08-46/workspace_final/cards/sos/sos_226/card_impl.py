"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power 1 "
            "or greater. When you do, copy the spell and you may choose new targets "
            "for the copy.)",
        )
        super().__init__(**kwargs)

    def get_granted_casualty_value(
        self,
        game: GameState,
        card: Any,
    ) -> int | None:
        controller = getattr(self, "controller", None)
        if controller is None:
            return None
        if not game.get_battlefield(controller).contains(self):
            return None

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None

        return 1
