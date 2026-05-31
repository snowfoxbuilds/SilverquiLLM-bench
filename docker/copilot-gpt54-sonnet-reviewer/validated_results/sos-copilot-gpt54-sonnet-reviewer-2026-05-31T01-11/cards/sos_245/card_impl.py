"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Creature
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
            "Affinity for creatures (This spell costs {1} less to cast for each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    @staticmethod
    def _count_controlled_creatures(game: GameState, controller: Any) -> int:
        if controller is None:
            return 0
        return sum(
            1
            for permanent in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )

    def cost_reduction(self, game: GameState) -> int:
        return self._count_controlled_creatures(game, self.controller)

    def on_controller_spell_cost_reduction(
        self,
        game: GameState,
        player: Any,
        spell: CardImpl,
    ) -> int:
        """Grant affinity for creatures to your instants and sorceries."""
        if getattr(self, "controller", None) is not player:
            return 0
        if spell is self:
            return 0

        card_types = getattr(spell, "card_types", set())
        if not card_types & {CardType.INSTANT, CardType.SORCERY}:
            return 0

        return self._count_controlled_creatures(game, player)
