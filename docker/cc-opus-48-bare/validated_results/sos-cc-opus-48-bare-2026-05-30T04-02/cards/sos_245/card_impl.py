"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.card import CardImpl
    from engine.game_state import GameState
    from engine.player import Player


def _creatures_controlled(player: Any) -> int:
    return sum(
        1
        for obj in player.zones[Zone.BATTLEFIELD].get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Elder Dragon — Legendary.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures\nFlying, deathtouch\nInstant and sorcery "
            "spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)
        self.colors = ["B", "G"]

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures — {1} less per creature you control."""
        controller = self.controller
        if controller is None:
            return 0
        return _creatures_controlled(controller)

    def spell_cost_reduction(
        self, game: "GameState", card: "CardImpl", controller: "Player"
    ) -> int:
        """Grant affinity for creatures to instant/sorcery spells you cast."""
        if controller is not self.controller:
            return 0
        types = getattr(card, "card_types", set())
        if CardType.INSTANT not in types and CardType.SORCERY not in types:
            return 0
        return _creatures_controlled(controller)
