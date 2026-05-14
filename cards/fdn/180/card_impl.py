"""Card implementation for Phyrexian Arena."""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class PhyrexianArena(Enchantment):
    """Phyrexian Arena — {1}{B}{B} — Draw a card, lose 1 life at upkeep.

    At the beginning of your upkeep, you draw a card and you lose 1 life.

    FDN collector number 180.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Phyrexian Arena")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "At the beginning of your upkeep, you draw a card and you lose 1 life.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass  # No immediate effect; trigger registered via register_triggers

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            controller = source.controller
            return controller is not None and controller is game.active_player

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            draw_card(game, controller)
            controller.life -= 1
            game.trigger_manager.fire_event(
                game,
                EventType.LOSES_LIFE,
                {"player": controller, "amount": 1},
            )

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.BEGINNING_OF_UPKEEP,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
