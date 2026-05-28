"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype, Zone

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
        kwargs.setdefault("colors", {Color.BLACK, Color.GREEN})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Witherbloom itself has affinity for creatures."""
        return self._count_controlled_creatures(game, self.controller)

    def get_granted_cost_reduction_for_spell(
        self,
        game: "GameState",
        card: CardImpl,
    ) -> int:
        """Grant affinity for creatures to your instants and sorceries."""
        controller = self.controller
        if controller is None:
            return 0
        if not controller.zones[Zone.BATTLEFIELD].contains(self):
            return 0
        if getattr(card, "controller", None) is not controller:
            return 0

        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return 0
        return self._count_controlled_creatures(game, controller)

    @staticmethod
    def _count_controlled_creatures(game: "GameState", controller: Any) -> int:
        if controller is None:
            return 0
        battlefield = game.get_battlefield(controller)
        return sum(
            1
            for permanent in battlefield.get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )
