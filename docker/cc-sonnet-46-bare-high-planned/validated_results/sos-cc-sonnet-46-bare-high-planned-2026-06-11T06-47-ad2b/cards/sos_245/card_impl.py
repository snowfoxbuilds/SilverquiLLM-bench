"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


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
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\nFlying, deathtouch\nInstant and sorcery "
            "spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: costs {1} less per creature you control."""
        return _count_creatures(game, self.controller)

    def spell_cost_reduction(self, game: "GameState", spell: Any) -> int:
        """Grant affinity for creatures to controller's instant/sorcery spells.

        Called by E3 in get_cost_reduction for each battlefield permanent.
        Returns creature count so that casting player's instants/sorceries
        cost {1} less per creature.
        """
        # Only reduce spells cast by Witherbloom's controller.
        if spell.controller is not self.controller:
            return 0
        return _count_creatures(game, self.controller)


def _count_creatures(game: Any, controller: Any) -> int:
    """Count creatures controlled by *controller* on the battlefield."""
    if controller is None:
        return 0
    count = 0
    for perm in game.get_battlefield(controller).get_all():
        if CardType.CREATURE in getattr(perm, "card_types", set()):
            count += 1
    return count
