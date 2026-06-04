"""Card implementation for Witherbloom, the Balancer (SOS #245)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _creatures_you_control(game: "GameState", controller: "Player") -> int:
    count = 0
    for obj in game.get_battlefield(controller).get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            count += 1
    return count


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 Legendary Elder Dragon.

    Affinity for creatures (costs {1} less per creature you control).
    Flying, deathtouch.
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
            "Affinity for creatures\nFlying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: {1} less per creature you control."""
        controller = self.controller
        if controller is None:
            return 0
        return _creatures_you_control(game, controller)

    def grants_cost_reduction(
        self, game: "GameState", card: Any, controller: "Player"
    ) -> int:
        """Grant affinity for creatures to your instant and sorcery spells."""
        types = getattr(card, "card_types", set())
        if types & {CardType.INSTANT, CardType.SORCERY}:
            return _creatures_you_control(game, controller)
        return 0
