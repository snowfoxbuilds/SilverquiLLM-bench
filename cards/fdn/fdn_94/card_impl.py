"""Card implementation for Slumbering Cerberus."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class SlumberingCerberus(Creature):
    """Slumbering Cerberus — {1}{R} — 4/2 — Dog.

    This creature doesn't untap during your untap step.
    Morbid — At the beginning of each end step, if a creature died this
    turn, untap this creature.

    FDN collector number 94.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Slumbering Cerberus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Dog"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "This creature doesn't untap during your untap step.\n"
            "Morbid — At the beginning of each end step, if a creature "
            "died this turn, untap this creature.",
        )
        super().__init__(**kwargs)
        # Mark as not untapping during untap step
        self.skip_untap = True

    def register_triggers(self, game: "GameState") -> None:
        """Register end-step Morbid trigger for untapping."""
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, data: dict) -> bool:
            # Morbid: a creature died this turn
            return getattr(game, "creature_died_this_turn", False)

        def _effect(game: "GameState") -> None:
            source.is_tapped = False
            source.tapped = False

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.END_STEP,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
