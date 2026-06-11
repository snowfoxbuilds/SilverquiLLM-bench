"""Card implementation for Burrog Barrage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class BurrogBarrage(Instant):
    """Burrog Barrage — {1}{G} — Instant.

    Target creature you control gets +1/+0 until end of turn if you've cast
    another instant or sorcery spell this turn. Then it deals damage equal to
    its power to up to one target creature an opponent controls.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burrog Barrage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        my_creature = targets[0]
        opponent_creature = targets[1] if len(targets) > 1 else None

        # Check if another instant/sorcery was cast this turn
        spells_cast = getattr(game, "spells_cast_this_turn", [])
        cast_another = any(
            spell is not self
            and (CardType.INSTANT in getattr(spell, "card_types", set())
                 or CardType.SORCERY in getattr(spell, "card_types", set()))
            for spell in spells_cast
        )

        if cast_another:
            # Give +1/+0 until end of turn
            my_creature._temp_power_bonus = getattr(my_creature, "_temp_power_bonus", 0) + 1

        # Deal damage equal to power to opponent creature
        if opponent_creature is not None:
            damage = my_creature.get_power()
            opponent_creature.damage_dealt_to_it = getattr(opponent_creature, "damage_dealt_to_it", 0) + damage
