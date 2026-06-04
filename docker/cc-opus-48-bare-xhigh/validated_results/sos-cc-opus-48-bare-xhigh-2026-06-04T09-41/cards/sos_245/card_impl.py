"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, CardImpl
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _count_creatures(controller: "Player") -> int:
    """Number of creatures *controller* controls (for affinity for creatures)."""
    return sum(
        1
        for c in controller.zones[Zone.BATTLEFIELD].get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Elder Dragon.

    Affinity for creatures (this spell costs {1} less per creature you
    control).  Flying, deathtouch.  Instant and sorcery spells you cast
    also have affinity for creatures.
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
            "Affinity for creatures\nFlying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: {1} less per creature you control."""
        controller = self.controller
        if controller is None:
            return 0
        return _count_creatures(controller)

    def static_cost_reduction(
        self, game: "GameState", card: CardImpl, controller: "Player"
    ) -> int:
        """Grant affinity for creatures to the controller's instant/sorcery spells."""
        if card.card_types & {CardType.INSTANT, CardType.SORCERY}:
            return _count_creatures(controller)
        return 0
