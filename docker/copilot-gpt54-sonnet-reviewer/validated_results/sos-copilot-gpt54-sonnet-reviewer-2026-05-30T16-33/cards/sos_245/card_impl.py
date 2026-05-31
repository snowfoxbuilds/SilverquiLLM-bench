"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs["keywords"] = (
            (kwargs.get("keywords") or Keyword(0))
            | Keyword.FLYING
            | Keyword.DEATHTOUCH
        )
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)
        self.mechanic_keywords: set[str] = {"Affinity"}

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures."""
        controller = self.controller
        if controller is None:
            return 0
        return sum(
            1
            for permanent in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )

    def get_affinity_reduction_for(
        self,
        game: "GameState",
        player: "Player",
        spell: Any,
    ) -> int | None:
        """Grant affinity for creatures to your instants and sorceries."""
        if self.controller is None or player is not self.controller:
            return None
        if self not in game.get_battlefield(self.controller).get_all():
            return None
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return None
        spell_controller = getattr(spell, "controller", None)
        if spell_controller is not None and spell_controller is not player:
            return None
        return sum(
            1
            for permanent in game.get_battlefield(player).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )
