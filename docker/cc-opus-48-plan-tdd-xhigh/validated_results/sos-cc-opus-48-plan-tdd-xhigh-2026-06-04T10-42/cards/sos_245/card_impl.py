"""Card implementation for Witherbloom, the Balancer (SOS #245)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_creatures(player: Any) -> int:
    """Number of creatures *player* controls on the battlefield."""
    if player is None:
        return 0
    battlefield = player.zones[Zone.BATTLEFIELD]
    return sum(
        1
        for obj in battlefield.get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Elder Dragon.

    Affinity for creatures (this spell costs {1} less to cast for each
    creature you control).
    Flying, deathtouch.
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Dragon", "Elder"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Self-affinity: {1} less per creature you control."""
        return _count_creatures(self.controller)

    def static_cost_reduction(
        self, game: "GameState", spell: Any, controller: Any
    ) -> int:
        """Grant affinity for creatures to the controller's instants/sorceries."""
        if controller is not self.controller:
            return 0
        types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in types and CardType.SORCERY not in types:
            return 0
        return _count_creatures(controller)
