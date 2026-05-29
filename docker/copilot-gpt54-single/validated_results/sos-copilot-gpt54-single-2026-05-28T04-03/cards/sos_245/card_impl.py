"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.card import CardImpl
    from engine.game_state import GameState
    from engine.player import Player


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def _count_controlled_creatures(self, game: "GameState", controller: "Player | None") -> int:
        if controller is None:
            return 0
        battlefield = game.get_battlefield(controller)
        return sum(
            1
            for obj in battlefield.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def cost_reduction(self, game: "GameState") -> int:
        return self._count_controlled_creatures(game, self.controller)

    def get_granted_cost_reduction(
        self,
        game: "GameState",
        card: "CardImpl",
        player: "Player | None" = None,
    ) -> int:
        controller = player if player is not None else self.controller or self.owner
        if controller is None or controller is not getattr(card, "controller", None):
            return 0
        if not getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}:
            return 0
        return self._count_controlled_creatures(game, controller)
