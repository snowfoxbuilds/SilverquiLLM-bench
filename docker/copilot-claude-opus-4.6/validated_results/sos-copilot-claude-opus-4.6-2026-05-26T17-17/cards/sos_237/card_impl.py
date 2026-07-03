"""Card implementation for Tam, Observant Sequencer // Deep Sight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class TamObservantSequencerDeepSight(Creature):
    """Tam, Observant Sequencer — {2}{G}{U} — Legendary Creature — Gorgon Wizard, 4/3.

    Landfall — Whenever a land you control enters, Tam becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tam, Observant Sequencer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        kwargs.setdefault("subtypes", {"Gorgon", "Wizard"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Landfall — Whenever a land you control enters, Tam becomes prepared.",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_land_enters(self, game: "GameState", player: Any) -> None:
        """Landfall trigger — Tam becomes prepared."""
        self.prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the prepared spell copy, unpreparing Tam."""
        self.prepared = False
