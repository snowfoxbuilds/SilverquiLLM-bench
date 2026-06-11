"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, CardImpl
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon.

    Affinity for creatures (This spell costs {1} less for each creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.
    5/5
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        super().__init__(**kwargs)

    def get_effective_cost(self, game: "GameState") -> ManaCost:
        """Affinity for creatures: costs {1} less per creature you control."""
        controller = self.controller or self.owner
        creature_count = self._count_creatures(game, controller)

        base = self.mana_cost
        new_generic = max(0, base.generic - creature_count)
        return ManaCost(generic=new_generic, pips=dict(base.pips), x_count=base.x_count)

    @staticmethod
    def _count_creatures(game: "GameState", player: Any) -> int:
        """Count creatures on the battlefield controlled by player."""
        bf = game.get_battlefield(player)
        count = 0
        for obj in bf.get_all():
            card_types = getattr(obj, "card_types", set())
            if CardType.CREATURE in card_types:
                count += 1
        return count

    def provide_cost_reduction(self, game: "GameState", spell: "CardImpl") -> int:
        """Grant affinity for creatures to instant and sorcery spells."""
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            controller = self.controller or self.owner
            return self._count_creatures(game, controller)
        return 0
