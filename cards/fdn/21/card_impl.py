"""Card implementation for Prideful Parent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.game import create_token
from engine.triggers import EventType, TriggerRegistration
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState




def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition
class PridefulParent(Creature):
    """Prideful Parent — {2}{W} — 2/2 — Cat — Vigilance

    When this creature enters, create a 1/1 white Cat creature token.

    FDN collector number 21.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Prideful Parent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Cat"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\nWhen this creature enters, create a 1/1 white Cat creature token.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                token = Creature(
                    name="Cat",
                    subtypes={"Cat"},
                    base_power=1,
                    base_toughness=1,
                    owner=controller,
                    controller=controller,
                )
                create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))
