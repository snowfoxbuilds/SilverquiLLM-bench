"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """This spell has affinity for creatures you control."""
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1
            for permanent in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )

    def granted_cost_reduction_for(self, game: "GameState", card: Any) -> int | None:
        """Grant your instants and sorceries affinity for creatures."""
        controller = self.controller
        if controller is None or getattr(card, "controller", None) is not controller:
            return None
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None
        return sum(
            1
            for permanent in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )
