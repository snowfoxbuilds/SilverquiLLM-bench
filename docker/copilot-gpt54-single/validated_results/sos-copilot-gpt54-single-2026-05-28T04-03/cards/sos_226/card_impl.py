"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.card import CardImpl
    from engine.game_state import GameState
    from engine.player import Player


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

    def __init__(self, **kwargs: object) -> None:
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
            "or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    def get_granted_casualty_value(
        self,
        game: "GameState",
        card: "CardImpl",
        player: "Player | None" = None,
    ) -> int | None:
        controller = player if player is not None else self.controller or self.owner
        if controller is None or controller is not getattr(card, "controller", None):
            return None
        if getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}:
            return 1
        return None
