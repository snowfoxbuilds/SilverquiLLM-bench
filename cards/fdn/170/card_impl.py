"""Card implementation for Burglar Rat."""

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

class BurglarRat(Creature):
    """Burglar Rat — {1}{B} — 1/1 — Rat

    When this creature enters, each opponent discards a card.

    FDN collector number 170.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burglar Rat")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Rat"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, each opponent discards a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import discard

        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            for player in game.players:
                if player is controller:
                    continue
                hand = game.get_hand(player)
                hand_cards = hand.get_all()
                if hand_cards:
                    try:
                        to_discard = player.choose_card(hand_cards)
                    except Exception:
                        to_discard = hand_cards[-1]
                    discard(game, player, to_discard)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))
