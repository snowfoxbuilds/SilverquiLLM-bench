"""Card implementation for Chelonian Tackle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ChelonianTackle(Sorcery):
    """Chelonian Tackle — {2}{G} — Sorcery.

    Target creature you control gets +0/+10 until end of turn.
    Then it fights up to one target creature an opponent controls.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Chelonian Tackle")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        my_creature = targets[0]
        opponent_creature = targets[1] if len(targets) > 1 else None

        # Give +0/+10 until end of turn
        my_creature._temp_toughness_bonus = getattr(my_creature, "_temp_toughness_bonus", 0) + 10

        # Fight: each deals damage equal to its power to the other
        if opponent_creature is not None:
            my_power = my_creature.get_power()
            opp_power = opponent_creature.get_power()
            opponent_creature.damage_dealt_to_it = getattr(opponent_creature, "damage_dealt_to_it", 0) + my_power
            my_creature.damage_dealt_to_it = getattr(my_creature, "damage_dealt_to_it", 0) + opp_power
