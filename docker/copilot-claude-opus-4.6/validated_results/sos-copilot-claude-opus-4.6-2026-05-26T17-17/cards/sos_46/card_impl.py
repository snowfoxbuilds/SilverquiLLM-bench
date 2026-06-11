"""Card implementation for Encouraging Aviator // Jump."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EncouragingAviatorJump(Creature):
    """Encouraging Aviator // Jump — {2}{U} — Creature — Bird Wizard — 2/3.

    Flying.
    Whenever this creature attacks, it becomes prepared.
    While prepared, you may cast a copy of Jump (the back face).
    Doing so unprepares it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Encouraging Aviator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", {"Bird", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger to become prepared."""
        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: Any) -> None:
            source.is_prepared = True

        controller = self.controller or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of the Jump spell (back face). Unprepares the creature."""
        self.is_prepared = False
