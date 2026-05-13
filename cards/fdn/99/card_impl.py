"""Card implementation for ApothecaryStomper."""

from __future__ import annotations


from engine.card import Creature, Instant, Mode, Sorcery
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


def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, "controller", None)

def _get_target(card: Any) -> Any:
    """Return the first chosen target or the _resolve_target fallback."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""
    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source
    return _condition


class ApothecaryStomper(Creature):
    """Apothecary Stomper — {4}{G}{G} — 4/4 — Elephant

    Vigilance.
    When this creature enters, choose one —
    - Put two +1/+1 counters on target creature you control.
    - You gain 4 life.

    FDN collector number 99.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Apothecary Stomper")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{G}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Elephant"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Counters", description="Put two +1/+1 counters on target creature you control."),
            Mode(name="Life", description="You gain 4 life."),
        ]

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        def _etb_effect(g: GameState) -> None:
            controller = _get_controller(self)
            if controller is None:
                return
            mode = self.chosen_mode
            if mode is None:
                # Default to mode 0
                mode = 0
            if mode == 0:
                target = _get_target(self)
                if target is None:
                    target = self
                if hasattr(target, "plus_one_counters"):
                    target.plus_one_counters += 2
                    target._original_plus_one_counters = target.plus_one_counters
            elif mode == 1:
                controller.life += 4

        reg = TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=self.controller or self.owner,
        )
        game.trigger_manager.register(reg)


__all__ = ["ApothecaryStomper"]
