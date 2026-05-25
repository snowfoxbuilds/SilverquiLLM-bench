"""Card implementation for Muldrotha, the Gravetide."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MuldrothaTheGravetide(Creature):
    """Muldrotha, the Gravetide — {3}{B}{G}{U} — 6/6 — Legendary Elemental Avatar.

    During each of your turns, you may play a land and cast a permanent
    spell of each permanent type from your graveyard.

    FDN collector number 243.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muldrotha, the Gravetide")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{G}{U}"))
        kwargs.setdefault("subtypes", {"Elemental", "Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 6)
        kwargs.setdefault(
            "rules_text",
            "During each of your turns, you may play a land and cast a "
            "permanent spell of each permanent type from your graveyard. "
            "(If a card has multiple permanent types, choose one as you "
            "play it.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register graveyard casting permission marker.

        ENGINE LIMITATION: Full graveyard casting requires engine-level
        support for alternative casting zones.  This registers a marker
        attribute that the casting system could consult, and tracks
        which permanent types have been used from the graveyard each turn.
        """
        self._allows_graveyard_casting = True
        # Track which permanent types have been cast from GY this turn
        self._gy_types_used_this_turn: set[str] = set()
        self._gy_land_played_this_turn: bool = False
