"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Elder Dragon.

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
        kwargs.setdefault("supertypes", {"Legendary"})
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

    def _creatures_controlled(self, game: GameState, controller: Any) -> int:
        if controller is None:
            return 0
        return sum(
            1
            for perm in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(perm, "card_types", set())
        )

    def cost_reduction(self, game: GameState) -> int:
        """Its own affinity for creatures (generic-only, engine clamps)."""
        return self._creatures_controlled(game, self.controller)

    def spell_cost_reduction(self, game: GameState, spell: Any) -> int:
        """Grant affinity for creatures to the controller's instant and
        sorcery spells — aggregated by ``get_cost_reduction`` while this
        permanent is on the battlefield (instant/sorcery gating happens
        there)."""
        return self._creatures_controlled(game, self.controller)
