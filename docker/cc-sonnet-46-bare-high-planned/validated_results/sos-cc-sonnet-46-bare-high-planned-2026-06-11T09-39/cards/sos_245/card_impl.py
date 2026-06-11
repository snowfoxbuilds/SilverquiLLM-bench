"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each creature
    you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.

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
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\nFlying, deathtouch\nInstant and sorcery spells "
            "you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: 1 less per creature you control (generic only)."""
        controller = self.controller
        if controller is None:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1 for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )

    def spell_cost_reduction(self, game: "GameState", spell: Any) -> int:
        """E3 hook: grant affinity for creatures to controller's instants/sorceries.

        Returns the number of creatures the controller controls so that
        get_cost_reduction aggregates it into other spells' costs.
        Deliberate limitation: only applies when this permanent is on the
        battlefield (E3 only checks the caster's battlefield).
        """
        controller = self.controller
        if controller is None:
            return 0
        # Only grant to this permanent's controller's own spells.
        if getattr(spell, "controller", None) is not controller:
            return 0
        bf = game.get_battlefield(controller)
        return sum(
            1 for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )
