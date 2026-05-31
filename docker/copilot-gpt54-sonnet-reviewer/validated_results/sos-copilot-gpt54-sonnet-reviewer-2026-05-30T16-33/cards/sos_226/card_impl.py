"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs["keywords"] = (kwargs.get("keywords") or Keyword(0)) | Keyword.FLYING | Keyword.VIGILANCE
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power "
            "1 or greater. When you do, copy the spell and you may choose "
            "new targets for the copy.)",
        )
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.mechanic_keywords: set[str] = {"Casualty"}
        self.keyword_metadata: dict[str, dict[str, Any]] = {
            "Casualty": {"amount": 1, "minimum_power": 1},
        }

    def get_casualty_value_for(
        self,
        game: "GameState",
        player: "Player",
        spell: Any,
    ) -> int | None:
        """Grant casualty 1 to your instants and sorceries on the battlefield."""
        if self.controller is None or player is not self.controller:
            return None
        if self not in game.get_battlefield(self.controller).get_all():
            return None
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None
        spell_controller = getattr(spell, "controller", None)
        if spell_controller is not None and spell_controller is not player:
            return None
        return self.keyword_metadata["Casualty"]["amount"]
