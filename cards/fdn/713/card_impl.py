"""Card implementation for GatekeeperOfMalakir."""

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


class GatekeeperOfMalakir(Creature):
    """Gatekeeper of Malakir — {B}{B} — 2/2 — Vampire Warrior

    Kicker {B}.
    When this creature enters, if it was kicked, target player
    sacrifices a creature of their choice.

    FDN collector number 713.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gatekeeper of Malakir")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", {"Vampire", "Warrior"})
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse("{B}")

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        def _etb_effect(g: GameState) -> None:
            if not self.kicked:
                return
            from engine.game import sacrifice
            target = _get_target(self)
            if target is None:
                return
            # Target player sacrifices a creature
            bf = g.get_battlefield(target)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    sacrifice(g, target, obj)
                    break

        reg = TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=self.controller or self.owner,
        )
        game.trigger_manager.register(reg)


__all__ = ["GatekeeperOfMalakir"]
