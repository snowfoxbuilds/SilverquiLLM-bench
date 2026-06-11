"""Card implementation for Poisoner's Apprentice."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PoisonersApprentice(Creature):
    """Poisoner's Apprentice — {2}{B} — Creature — Orc Warlock.

    2/2. Infusion — When this creature enters, target creature an opponent
    controls gets -4/-4 until end of turn if you gained life this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Poisoner's Apprentice")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Orc", "Warlock"})
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: If controller gained life this turn, target gets -4/-4."""
        controller = self.controller
        targets = getattr(self, "chosen_targets", None) or getattr(self, "_explicit_targets", [])

        life_gained = getattr(controller, "life_gained_this_turn", 0)

        if life_gained > 0 and targets:
            target = targets[0]
            # Apply -4/-4 until end of turn
            target._temp_power_bonus = getattr(target, "_temp_power_bonus", 0) - 4
            target._temp_toughness_bonus = getattr(target, "_temp_toughness_bonus", 0) - 4

            # Check SBA: if toughness <= 0, destroy
            from engine.game import destroy
            if target.get_toughness(game) <= 0:
                destroy(game, target)
