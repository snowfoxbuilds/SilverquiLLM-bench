"""Card implementation for Spirit Mascot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import GraveyardLeaveTriggeredEvent
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SpiritMascot(Creature):
    """Spirit Mascot — {R}{W} — 2/2 — Creature — Spirit Ox.

    Whenever one or more cards leave your graveyard, put a +1/+1 counter
    on this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spirit Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("subtypes", {"Spirit", "Ox"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register graveyard leave trigger."""
        pass

    def on_graveyard_leave(self, game: "GameState", event: Any) -> None:
        """Whenever one or more cards leave controller's graveyard,
        put a +1/+1 counter on this creature."""
        event_player = getattr(event, "player", None)
        if event_player is not self.controller:
            return

        self.plus_one_counters += 1
        self._base_plus_one_counters = self.plus_one_counters
