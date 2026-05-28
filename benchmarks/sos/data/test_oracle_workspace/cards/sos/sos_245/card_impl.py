"""Card implementation for Witherbloom, the Balancer.

{6}{B}{G} 5/5 Legendary Creature — Elder Dragon
Affinity for creatures (This spell costs {1} less to cast for each creature
you control.)
Flying, deathtouch
Instant and sorcery spells you cast have affinity for creatures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
)

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — Legendary Elder Dragon.

    Flying, deathtouch.
    Affinity for creatures (own cost reduced by number of creatures you control).
    Static: Instant and sorcery spells controller casts have affinity for
    creatures.  The grant is implemented via the ``affinity_for_creatures_grant``
    attribute, which the engine's casting pipeline checks when casting
    instants/sorceries.
    """

    def __init__(
        self,
        name: str = "Witherbloom, the Balancer",
        owner: Any = None,
        base_power: int = 5,
        base_toughness: int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            mana_cost=ManaCost(generic=6, pips={ManaType.BLACK: 1, ManaType.GREEN: 1}),
            card_types={CardType.CREATURE},
            subtypes={"Elder", "Dragon"},
            supertypes={Supertype.LEGENDARY},
            keywords=Keyword.FLYING | Keyword.DEATHTOUCH | Keyword.AFFINITY,
            rules_text=(
                "Affinity for creatures (This spell costs {1} less to cast "
                "for each creature you control.)\n"
                "Flying, deathtouch\n"
                "Instant and sorcery spells you cast have affinity for creatures."
            ),
            owner=owner,
            base_power=base_power,
            base_toughness=base_toughness,
            **kwargs,
        )
        # The affinity_for_creatures_grant attribute is checked by the casting
        # pipeline.  When this creature is on the battlefield, the pipeline
        # sees it and applies affinity-for-creatures cost reduction to
        # controller's instants and sorceries.
        self.affinity_for_creatures_grant: bool = True

    def cost_reduction(self, game: GameState) -> int:
        """Affinity for creatures — reduce cost by number of creatures controller controls."""
        if self.controller is None:
            return 0
        bf = game.get_battlefield(self.controller)
        count = 0
        for perm in bf.get_all():
            if CardType.CREATURE in getattr(perm, "card_types", set()):
                count += 1
        return count
