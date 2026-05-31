"""Card implementation for Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.card import CardImpl
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} Legendary Creature — Elder Dragon 5/5.

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

    def _count_creatures(self, game: "GameState") -> int:
        """Return the number of creatures the controller controls."""
        controller = self.controller
        if controller is None:
            return 0
        battlefield = controller.zones[Zone.BATTLEFIELD]
        count = 0
        for permanent in battlefield.get_all():
            types = getattr(permanent, "card_types", set())
            if CardType.CREATURE in types:
                count += 1
        return count

    def cost_reduction(self, game: "GameState") -> int:
        """Return 1 less per creature the controller controls (own affinity)."""
        return self._count_creatures(game)

    def grants_cost_reduction(self, game: "GameState", spell_card: "CardImpl") -> int:
        """Grant affinity for creatures to instants/sorceries cast by controller.

        While Witherbloom is on the battlefield, instant and sorcery spells
        cast by its controller cost {1} less for each creature that controller
        controls.
        """
        types = getattr(spell_card, "card_types", set())
        if CardType.INSTANT not in types and CardType.SORCERY not in types:
            return 0
        # The spell_card's controller is set to the casting player by
        # get_cost_reduction() before calling us via get_external_cost_reduction.
        # We check that it matches Witherbloom's controller.
        spell_controller = getattr(spell_card, "controller", None)
        if spell_controller is not self.controller:
            return 0
        return self._count_creatures(game)

