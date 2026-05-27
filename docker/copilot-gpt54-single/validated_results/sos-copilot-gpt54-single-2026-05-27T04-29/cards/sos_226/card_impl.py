"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("colors", {Color.WHITE, Color.BLACK})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power 1 or greater. "
            "When you do, copy the spell and you may choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def get_granted_casualty_value(
        self,
        game: "GameState",
        card: Any,
        player: Any | None = None,
    ) -> int | None:
        """Grant casualty 1 to instant and sorcery spells you cast."""
        controller = player if player is not None else self.controller
        if controller is None:
            return None
        if not game.get_battlefield(controller).contains(self):
            return None
        if not _is_instant_or_sorcery(card):
            return None
        return 1
