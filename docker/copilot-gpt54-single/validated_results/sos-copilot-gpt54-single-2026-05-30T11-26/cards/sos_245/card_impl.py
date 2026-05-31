"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from engine.card import CardImpl


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
        self.set_base_colors({Color.BLACK, Color.GREEN})

    @staticmethod
    def _count_creatures_you_control(game: "GameState", player: "Player" | None) -> int:
        if player is None:
            return 0
        return sum(
            1
            for permanent in game.get_battlefield(player).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )

    def cost_reduction(self, game: "GameState") -> int:
        return self._count_creatures_you_control(game, self.controller or self.owner)

    def granted_cost_reduction(
        self,
        game: "GameState",
        spell: "CardImpl",
        caster: "Player",
        mana_cost: ManaCost | None = None,
    ) -> int:
        if self.controller is not caster:
            return 0
        if not game.get_battlefield(caster).contains(self):
            return 0
        if not getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}:
            return 0
        return self._count_creatures_you_control(game, caster)
