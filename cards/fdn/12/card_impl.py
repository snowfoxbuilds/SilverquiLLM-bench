"""Card implementation for FelidarSavior."""

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

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


class FelidarSavior(Creature):
    """Felidar Savior — {3}{W} — 2/3 — Cat Beast — Lifelink

    When this creature enters, put a +1/+1 counter on each of up to two
    other target creatures you control.

    FDN collector number 12.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Felidar Savior")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Beast"})
        kwargs.setdefault("keywords", Keyword.LIFELINK)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Lifelink\nWhen this creature enters, put a +1/+1 counter on each of "
            "up to two other target creatures you control.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import add_counter

        source = self

        def _effect(game: GameState) -> None:
            # Get targets from chosen_targets (up to 2)
            chosen = getattr(source, "chosen_targets", None)
            if not chosen:
                targets_list = getattr(source, "_resolve_targets", None)
                if targets_list:
                    chosen = targets_list
                else:
                    target = getattr(source, "_resolve_target", None)
                    if target is not None:
                        chosen = [target]
            if not chosen:
                return
            for target in chosen[:2]:
                if target is not source and _is_on_battlefield(game, target):
                    add_counter(game, target, "+1/+1", 1)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["FelidarSavior"]
