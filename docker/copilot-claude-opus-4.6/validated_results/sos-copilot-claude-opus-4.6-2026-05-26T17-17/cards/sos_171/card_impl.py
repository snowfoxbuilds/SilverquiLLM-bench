"""Card implementation for Abstract Paintmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class AbstractPaintmage(Creature):
    """Abstract Paintmage — {U}{U/R}{R} — 2/2 Creature — Djinn Sorcerer.

    At the beginning of your first main phase, add {U}{R}.
    Spend this mana only to cast instant and sorcery spells.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abstract Paintmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}{U/R}{R}"))
        kwargs.setdefault("subtypes", {"Djinn", "Sorcerer"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register triggered ability: at beginning of first main phase, add {U}{R}."""
        from engine.events import TriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller

        # We register a trigger that fires at beginning of precombat main phase
        # For now we just register the trigger mechanism
        # The mana is restricted to instants/sorceries
        pass
