"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
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
            for obj in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def cost_reduction(self, game: GameState) -> int:
        """Own affinity for creatures: {1} less per creature you control."""
        return self._creatures_controlled(game, self.controller)

    def spell_cost_reduction(self, game: GameState, spell: Any) -> int:
        """Grant: your instant/sorcery spells have affinity for creatures.

        Aggregated by ``get_cost_reduction`` (which already restricts to
        instants/sorceries cast by this card's controller).
        """
        return self._creatures_controlled(game, self.controller)
