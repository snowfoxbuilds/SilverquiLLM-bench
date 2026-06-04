"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


def _creature_count(game: "GameState", controller: Any) -> int:
    bf = game.get_battlefield(controller)
    return sum(
        1 for c in bf.get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Elder Dragon.

    Affinity for creatures (this spell costs {1} less to cast for each
    creature you control). Flying, deathtouch. Instant and sorcery spells
    you cast have affinity for creatures.

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
            "Affinity for creatures\nFlying, deathtouch\nInstant and sorcery "
            "spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        controller = self.controller
        if controller is None:
            return 0
        return _creature_count(game, controller)

    def grants_cost_reduction(
        self, game: "GameState", card: Any, controller: Any
    ) -> int:
        """Grant affinity for creatures to this controller's instants/sorceries."""
        if self.controller is None or controller is not self.controller:
            return 0
        if not _is_instant_or_sorcery(card):
            return 0
        return _creature_count(game, self.controller)
