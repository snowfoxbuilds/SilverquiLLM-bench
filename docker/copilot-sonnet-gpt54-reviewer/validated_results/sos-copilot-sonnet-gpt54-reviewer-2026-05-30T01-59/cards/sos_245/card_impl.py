"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon (5/5).

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\nFlying, deathtouch\nInstant and sorcery spells "
            "you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def _count_creatures(self, game: "GameState", controller: Any) -> int:
        """Count creatures *controller* controls on the battlefield."""
        bf = game.get_battlefield(controller)
        return sum(
            1
            for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} reduction per creature the controller controls (self affinity)."""
        controller = self.controller
        if controller is None:
            return 0
        return self._count_creatures(game, controller)

    def global_cost_reduction_for(
        self,
        game: "GameState",
        card: Any,
        controller: "Player",
    ) -> int:
        """Grant affinity for creatures to instants and sorceries cast by our controller."""
        # Only grant reduction to our own controller
        if self.controller is not controller:
            return 0
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return 0
        return self._count_creatures(game, controller)

