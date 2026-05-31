"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.

    ENGINE EXTENSION: ``get_spell_cost_reduction`` is called by the casting
    pipeline (engine/casting.py) when Witherbloom is on the battlefield.
    It grants affinity-for-creatures to instants/sorceries cast by the
    controller.

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
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\nFlying, deathtouch\nInstant and "
            "sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Self cost reduction (affinity for creatures)
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} per creature the controller controls."""
        return self._count_controller_creatures(game)

    # ------------------------------------------------------------------
    # Spell cost reduction for others (continuous effect hook)
    # ------------------------------------------------------------------

    def get_spell_cost_reduction(
        self, game: "GameState", card: Any, casting_player: Any
    ) -> int:
        """Grant affinity-for-creatures to instants/sorceries cast by controller.

        Called by the casting pipeline in ``engine/casting.get_cost_reduction``.
        """
        my_controller = self.controller
        if my_controller is None or casting_player is not my_controller:
            return 0
        # Only applies to instants and sorceries (not to Witherbloom itself).
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return 0
        return self._count_controller_creatures(game)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _count_controller_creatures(self, game: "GameState") -> int:
        """Count creatures the controller currently controls on the battlefield."""
        controller = self.controller
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1 for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )

