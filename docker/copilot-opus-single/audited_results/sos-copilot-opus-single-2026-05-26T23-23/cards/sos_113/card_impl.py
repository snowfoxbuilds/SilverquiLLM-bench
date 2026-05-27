"""Card implementation for Emeritus of Conflict // Lightning Bolt."""

from __future__ import annotations

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class EmeritusOfConflictLightningBolt(Creature):
    """Emeritus of Conflict // Lightning Bolt.

    A 2/2 Red Human Wizard with first strike for {1}{R}.
    Whenever you cast your third spell each turn, this creature becomes prepared.
    While prepared, you may cast a copy of Lightning Bolt (deal 3 damage to any
    target). Doing so unprepares it.
    """

    def __init__(self, owner: Player | None = None, **kwargs: Any) -> None:
        super().__init__(
            name="Emeritus of Conflict",
            mana_cost=ManaCost.parse("{1}{R}"),
            card_types={CardType.CREATURE},
            subtypes={"Human", "Wizard"},
            keywords={Keyword.FIRST_STRIKE},
            rules_text=(
                "First strike\n"
                "Whenever you cast your third spell each turn, "
                "this creature becomes prepared."
            ),
            owner=owner,
            base_power=2,
            base_toughness=2,
            **kwargs,
        )
        self.is_prepared: bool = False
        self._spells_cast_count: int = 0

    def on_spell_cast(self, game: GameState, event: Any) -> None:
        """Track spells cast by this creature's controller this turn."""
        # Only count spells cast by the controller of this creature
        caster = getattr(event, 'player', None) or getattr(event, 'controller', None)
        if caster is not self.controller:
            return

        self._spells_cast_count += 1
        if self._spells_cast_count == 3:
            self.is_prepared = True

    def cast_prepared_spell(self, game: GameState, target: Any) -> None:
        """Cast a copy of Lightning Bolt — deal 3 damage to any target."""
        if not self.is_prepared:
            raise ValueError("Cannot cast prepared spell: creature is not prepared.")

        # Deal 3 damage to target
        from engine.card import Creature as _Creature
        if isinstance(target, _Creature):
            target.damage_marked += 3
        else:
            # Assume it's a player
            target.life -= 3

        # Unprepare
        self.is_prepared = False

    def on_turn_start(self, game: GameState) -> None:
        """Reset spell count at the start of each turn."""
        self._spells_cast_count = 0
