"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from engine.card import CardImpl


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — Legendary Creature — Elder Dragon (5/5).

    Affinity for creatures (This spell costs {1} less to cast for each creature
    you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", {Keyword.FLYING, Keyword.DEATHTOUCH})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: {1} less for each creature you control."""
        ctrl = getattr(self, "controller", None)
        if ctrl is None or not hasattr(game, "get_battlefield"):
            return 0
        bf = game.get_battlefield(ctrl)
        return sum(1 for c in bf.get_all() if isinstance(c, Creature))

    def grant_cost_reduction(
        self, game: "GameState", card: "CardImpl", controller: "Player"
    ) -> int:
        """Grant affinity for creatures to instants and sorceries you cast."""
        from engine.card import Instant, Sorcery

        ctrl = getattr(self, "controller", None)
        if ctrl is None or ctrl is not controller:
            return 0
        if not isinstance(card, (Instant, Sorcery)):
            return 0
        bf = game.get_battlefield(ctrl)
        return sum(1 for c in bf.get_all() if isinstance(c, Creature))
