"""Card implementation for Spiritcall Enthusiast // Scrollboost."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SpiritcallEnthusiastScrollboost(Creature):
    """Spiritcall Enthusiast // Scrollboost — {2}{W} — Creature — Cat Cleric — 3/3.

    Whenever one or more tokens you control enter, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spiritcall Enthusiast // Scrollboost")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Whenever one or more tokens you control enter, this creature "
            "becomes prepared. (While it's prepared, you may cast a copy of "
            "its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register the token-enters trigger."""
        source = self

        def _condition(game: Any, event: Any) -> bool:
            permanent = getattr(event, "permanent", None)
            if permanent is None:
                return False
            if not getattr(permanent, "is_token", False):
                return False
            # Must be controlled by same controller as this creature
            perm_controller = getattr(permanent, "controller", None)
            return perm_controller is source.controller

        def _effect(game: Any) -> None:
            source.is_prepared = True

        trigger = TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=source.controller,
        )
        game.trigger_manager.register(trigger)

    def on_enters_battlefield(self, game: "GameState", event: Any) -> None:
        """Handle ETB events for tokens entering under our control."""
        permanent = getattr(event, "permanent", None)
        if permanent is None:
            return
        if not getattr(permanent, "is_token", False):
            return
        perm_controller = getattr(permanent, "controller", None)
        if perm_controller is self.controller:
            self.is_prepared = True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the spell copy, unpreparing the creature."""
        self.is_prepared = False
