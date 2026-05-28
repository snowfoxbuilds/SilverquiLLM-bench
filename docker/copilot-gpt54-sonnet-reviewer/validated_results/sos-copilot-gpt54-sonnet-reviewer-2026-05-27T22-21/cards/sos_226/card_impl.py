"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype, Zone

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
        kwargs.setdefault("colors", {Color.BLACK, Color.WHITE})
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

    def get_granted_casualty_values_for_spell(
        self,
        game: "GameState",
        card: CardImpl,
    ) -> list[int]:
        controller = self.controller
        if controller is None:
            return []
        if not controller.zones[Zone.BATTLEFIELD].contains(self):
            return []
        if getattr(card, "controller", None) is not controller:
            return []

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return []
        return [1]
