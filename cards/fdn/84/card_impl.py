"""Card implementation for Dragon Trainer."""

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
class DragonTrainer(Creature):
    """Dragon Trainer — {3}{R}{R} — 1/1 — Human

    When this creature enters, create a 4/4 red Dragon creature token with flying.

    FDN collector number 84.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dragon Trainer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{R}"))
        kwargs.setdefault("subtypes", {"Human"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, create a 4/4 red Dragon creature token with flying.",
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
                    name="Dragon",
                    subtypes={"Dragon"},
                    keywords=Keyword.FLYING,
                    base_power=4,
                    base_toughness=4,
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
