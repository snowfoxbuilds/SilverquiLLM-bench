"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each creature
    you control.)
    Flying, deathtouch.
    Instant and sorcery spells you cast have affinity for creatures.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
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

    def _count_creatures(self, game: "GameState") -> int:
        """Count creatures the controller controls on the battlefield."""
        controller = self.controller
        if controller is None:
            return 0
        count = 0
        for card in game.get_battlefield(controller).get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.CREATURE in card_types:
                count += 1
        return count

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: {1} less for each creature you control."""
        return self._count_creatures(game)

    def get_spell_cost_reduction(self, game: "GameState", spell: Any) -> int:
        """Return cost reduction for instants/sorceries cast by the controller.

        Grants affinity for creatures to instants and sorceries.
        """
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return self._count_creatures(game)
        return 0
