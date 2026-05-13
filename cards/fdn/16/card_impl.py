"""Card implementation for Helpful Hunter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.game import draw_card
from engine.triggers import EventType, TriggerRegistration
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState




def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition
class HelpfulHunter(Creature):
    """Helpful Hunter — {1}{W} — 1/1 — Cat

    When this creature enters, draw a card.

    FDN collector number 16.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Helpful Hunter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Cat"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))
