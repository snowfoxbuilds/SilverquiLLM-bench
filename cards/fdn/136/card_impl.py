"""Card implementation for AngelOfFinality."""

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

def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


class AngelOfFinality(Creature):
    """Angel of Finality — {3}{W} — 3/4 — Angel — Flying

    When this creature enters, exile target player's graveyard.

    FDN collector number 136.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Angel of Finality")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Angel"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhen this creature enters, exile target player's graveyard.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            # Target a player — use chosen_targets or default to opponent
            target = _get_chosen_target(source, game)
            if target is None:
                # Default to first opponent
                controller = getattr(source, "controller", None)
                for player in game.players:
                    if player is not controller:
                        target = player
                        break
            if target is None:
                return
            # If target is a player, exile their graveyard
            if hasattr(target, "zones"):
                gy = target.zones[Zone.GRAVEYARD]
                exile = target.zones[Zone.EXILE]
                for card in gy.get_all():
                    gy.remove(card)
                    exile.add(card)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["AngelOfFinality"]
