"""Card implementation for CharmingPrince."""

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

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""
    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source
    return _condition


class CharmingPrince(Creature):
    """Charming Prince — {1}{W} — 2/2 — Human Noble

    When this creature enters, choose one —
    - Scry 2.
    - You gain 3 life.
    - Exile another target creature you own. Return it at the beginning
      of the next end step.

    FDN collector number 568.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Charming Prince")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Human", "Noble"})
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Scry", description="Scry 2."),
            Mode(name="Life", description="You gain 3 life."),
            Mode(name="Flicker", description="Exile another target creature you own. Return it at the beginning of the next end step."),
        ]

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        def _etb_effect(g: GameState) -> None:
            controller = _get_controller(self)
            if controller is None:
                return
            mode = self.chosen_mode
            if mode is None:
                mode = 0
            if mode == 0:
                # Scry 2 — simplified: look at top 2, keep on top
                pass  # ENGINE LIMITATION: scry not implemented
            elif mode == 1:
                controller.life += 3
            elif mode == 2:
                # Flicker target creature
                from engine.game import exile
                target = _get_target(self)
                if target is not None and target is not self and _is_on_battlefield(g, target):
                    exile(g, target)
                    # ENGINE LIMITATION: delayed trigger "return at beginning of
                    # next end step" not implemented — flicker is permanent exile

        reg = TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=self.controller or self.owner,
        )
        game.trigger_manager.register(reg)


__all__ = ["CharmingPrince"]
