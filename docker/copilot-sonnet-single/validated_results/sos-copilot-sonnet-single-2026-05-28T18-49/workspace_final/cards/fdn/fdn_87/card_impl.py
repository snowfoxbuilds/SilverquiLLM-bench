"""Card implementation for Goblin Boarders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class GoblinBoarders(Creature):
    """Goblin Boarders — {2}{R} — 3/2 — Goblin Pirate.

    Raid — This creature enters with a +1/+1 counter on it if you
    attacked this turn.

    FDN collector number 87.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Boarders")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Pirate"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Raid — This creature enters with a +1/+1 counter on it if "
            "you attacked this turn.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: Raid — enters with a +1/+1 counter if attacked this turn."""
        from engine.game import add_counter

        controller = self.controller
        if controller is None:
            return

        attacked_this_turn = getattr(game, "attacked_this_turn", False)
        if not attacked_this_turn:
            combat = getattr(game, "combat", None)
            if combat is not None:
                attackers = getattr(combat, "attackers", [])
                for attacker in attackers:
                    if getattr(attacker, "controller", None) is controller:
                        attacked_this_turn = True
                        break
        if not attacked_this_turn:
            attacked_this_turn = getattr(controller, "attacked_this_turn", False)

        if attacked_this_turn:
            add_counter(game, self, "+1/+1")
