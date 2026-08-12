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

    def enters_battlefield_with(self, game: "GameState", event: Any) -> None:
        """Raid — enters with a +1/+1 counter if you attacked this turn (614.1c).

        The Raid condition is read from game state as the creature enters, so
        the counter is on it *as* it enters rather than added one step late.
        Reads ``attacked_this_turn`` (per-player, else the game-level flag or the
        live combat's attackers). In replay this flag is not driven: GRE applies
        Goblin Boarders' raid counter one snapshot *after* entry (a counter
        cadence, issue #42), so entering with it at engine-entry-time would
        diverge from GRE by a snapshot — the raid counter is left as a cadence
        divergence rather than fabricated here.
        """
        controller = event.controller
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
            event.counters["+1/+1"] = event.counters.get("+1/+1", 0) + 1
