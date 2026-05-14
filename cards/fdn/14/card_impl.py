"""Card implementation for Guarded Heir."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition

class GuardedHeir(Creature):
    """Guarded Heir — {5}{W} — 1/1 — Human Noble — Lifelink

    When this creature enters, create two 3/3 white Knight creature tokens.

    FDN collector number 14.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Guarded Heir")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Noble"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Lifelink\nWhen this creature enters, create two 3/3 white Knight creature tokens.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                for _ in range(2):
                    token = Creature(
                        name="Knight",
                        subtypes={"Knight"},
                        base_power=3,
                        base_toughness=3,
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
