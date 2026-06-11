"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Elder Dragon 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast also have affinity for creatures.

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
            "sorcery spells you cast also have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: costs {1} less per creature you control."""
        controller = self.controller
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1 for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )

    def spell_cost_reduction(self, game: "GameState", spell: Any) -> int:
        """Grant affinity for creatures to controller's instants/sorceries (E3 hook).

        Called by get_cost_reduction (E3) when computing the cost of any
        instant/sorcery cast while Witherbloom is on the battlefield.
        Returns creature count only for spells cast by this card's controller.
        """
        controller = self.controller
        if controller is None:
            return 0
        spell_controller = getattr(spell, "controller", None)
        if spell_controller is not controller:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1 for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )
