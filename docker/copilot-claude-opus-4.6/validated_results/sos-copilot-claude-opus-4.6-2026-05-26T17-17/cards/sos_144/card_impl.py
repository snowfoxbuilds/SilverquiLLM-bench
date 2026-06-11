"""Card implementation for Efflorescence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class Efflorescence(Instant):
    """Efflorescence — {2}{G} — Instant.

    Put two +1/+1 counters on target creature.
    Infusion — If you gained life this turn, that creature also gains
    trample and indestructible until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Efflorescence")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        target = targets[0]

        # Put two +1/+1 counters
        target.plus_one_counters = getattr(target, "plus_one_counters", 0) + 2

        # Infusion: if controller gained life this turn, grant trample + indestructible
        controller = self.controller
        life_gained = getattr(controller, "life_gained_this_turn", 0)
        if life_gained > 0:
            target.keywords = target.keywords | Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE
