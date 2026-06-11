"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _creatures_you_control(game: "GameState", player: "Player") -> int:
    return sum(
        1 for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


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
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["keywords"] = (kwargs.get("keywords") or Keyword(0)) | Keyword.FLYING | Keyword.DEATHTOUCH
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\nFlying, deathtouch\nInstant and sorcery "
            "spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures — for casting Witherbloom itself."""
        controller = self.controller
        if controller is None:
            return 0
        return _creatures_you_control(game, controller)

    def spell_cost_reduction(self, game: "GameState", spell: Any) -> int:
        """Grant affinity for creatures to this controller's instant/sorcery
        spells (aggregated by ``get_cost_reduction`` — E3)."""
        controller = self.controller
        if controller is None:
            return 0
        return _creatures_you_control(game, controller)
