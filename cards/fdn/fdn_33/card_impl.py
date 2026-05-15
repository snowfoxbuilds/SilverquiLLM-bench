"""Card implementation for Clinquant Skymage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ClinquantSkymage(Creature):
    """Clinquant Skymage — {3}{U} — 1/1 — Bird Wizard — Flying.

    Whenever you draw a card, put a +1/+1 counter on this creature.

    FDN collector number 33.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Clinquant Skymage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Bird", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhenever you draw a card, put a +1/+1 counter on "
            "this creature.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register draw trigger: +1/+1 counter on each card drawn."""
        from engine.game import add_counter
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _draw_condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return data.get("player") is ctrl

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
