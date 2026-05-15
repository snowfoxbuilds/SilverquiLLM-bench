"""Card implementation for Erudite Wizard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EruditeWizard(Creature):
    """Erudite Wizard — {2}{U} — 2/3 — Human Wizard.

    Whenever you draw your second card each turn, put a +1/+1 counter on
    this creature.

    FDN collector number 37.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Erudite Wizard")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Whenever you draw your second card each turn, put a +1/+1 "
            "counter on this creature.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register draw trigger: second card drawn each turn → +1/+1 counter."""
        from engine.game import add_counter
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Track draws per turn
        source._erudite_draws_this_turn: int = 0
        source._erudite_last_turn: int = -1

        def _draw_condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if data.get("player") is not ctrl:
                return False
            # Reset counter on new turn
            current_turn = getattr(game, "turn_number", 0)
            if getattr(source, "_erudite_last_turn", -1) != current_turn:
                source._erudite_draws_this_turn = 0
                source._erudite_last_turn = current_turn
            source._erudite_draws_this_turn += 1
            # Trigger only on the second draw
            return source._erudite_draws_this_turn == 2

        def _draw_effect(game: "GameState") -> None:
            add_counter(game, source, "+1/+1", 1)
            if hasattr(source, "_original_plus_one_counters"):
                source._original_plus_one_counters = source.plus_one_counters

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.DRAWS_CARD,
            condition=_draw_condition,
            effect=_draw_effect,
            source=self,
            controller=controller,
        ))
