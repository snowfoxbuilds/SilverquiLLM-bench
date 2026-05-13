"""Card implementation for PelakkaWurm."""

from __future__ import annotations


from engine.card import ArtifactCreature, Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition


class PelakkaWurm(Creature):
    """Pelakka Wurm — {4}{G}{G}{G} — 7/7 — Wurm — Trample

    When this creature enters, you gain 7 life.
    When this creature dies, draw a card.

    FDN collector number 720.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pelakka Wurm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{G}{G}"))
        kwargs.setdefault("subtypes", {"Wurm"})
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "Trample\nWhen this creature enters, you gain 7 life.\n"
            "When this creature dies, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _etb_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.life += 7

        def _dies_condition(game: GameState, data: dict) -> bool:
            return data.get("creature") is source

        def _dies_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None) or getattr(source, "owner", None)
            if controller is not None:
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["PelakkaWurm"]
