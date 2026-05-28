"""Card implementation for Silverquill, the Disputant.

{2}{W}{B} 4/4 Legendary Creature — Elder Dragon
Flying, vigilance
Each instant and sorcery spell you cast has casualty 1.
(As you cast that spell, you may sacrifice a creature with power 1 or
greater. When you do, copy the spell and you may choose new targets for
the copy.)
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


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — Legendary Elder Dragon.

    Flying, vigilance.
    Static: Each instant and sorcery spell controller casts has casualty 1.
    The casualty grant is implemented via the ``casualty_grant`` attribute,
    which the engine's casting pipeline checks when casting instants/sorceries.
    """

    def __init__(
        self,
        name: str = "Silverquill, the Disputant",
        owner: Any = None,
        base_power: int = 4,
        base_toughness: int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            mana_cost=ManaCost(generic=2, pips={ManaType.WHITE: 1, ManaType.BLACK: 1}),
            card_types={CardType.CREATURE},
            subtypes={"Elder", "Dragon"},
            supertypes={Supertype.LEGENDARY},
            keywords=Keyword.FLYING | Keyword.VIGILANCE,
            rules_text=(
                "Flying, vigilance\n"
                "Each instant and sorcery spell you cast has casualty 1. "
                "(As you cast that spell, you may sacrifice a creature with "
                "power 1 or greater. When you do, copy the spell and you may "
                "choose new targets for the copy.)"
            ),
            owner=owner,
            base_power=base_power,
            base_toughness=base_toughness,
            **kwargs,
        )
        # The casualty_grant attribute is checked by the casting pipeline.
        # When this creature is on the battlefield, the pipeline sees it
        # and offers casualty 1 to the controller when casting instants/sorceries.
        self.casualty_grant: int = 1
