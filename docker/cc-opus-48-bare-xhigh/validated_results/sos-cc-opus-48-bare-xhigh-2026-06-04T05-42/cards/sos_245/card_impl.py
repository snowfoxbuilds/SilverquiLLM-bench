"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _creature_count(game: "GameState", controller: "Player") -> int:
    """Count creatures *controller* controls on the battlefield."""
    if controller is None:
        return 0
    count = 0
    for obj in game.get_battlefield(controller).get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            count += 1
    return count


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 Legendary Elder Dragon.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch.
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures\n"
            "Flying, deathtouch.\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)
        self.colors = ["B", "G"]

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: {1} less per creature you control."""
        return _creature_count(game, self.controller)

    def static_cost_reduction(
        self, game: "GameState", spell: Any, controller: "Player"
    ) -> int:
        """Grant affinity for creatures to instants/sorceries you cast."""
        if self.controller is not controller:
            return 0
        types = getattr(spell, "card_types", set())
        if CardType.INSTANT in types or CardType.SORCERY in types:
            return _creature_count(game, controller)
        return 0
