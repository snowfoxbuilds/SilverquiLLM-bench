"""Card implementation for Mischievous Pup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.triggers import EventType, TriggerRegistration
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState




def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition
class MischievousPup(Creature):
    """Mischievous Pup — {2}{W} — 3/1 — Dog

    When this creature enters, return up to one other target permanent you
    control to its owner's hand.

    FDN collector number 144.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mischievous Pup")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Dog"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, return up to one other target permanent "
            "you control to its owner's hand.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is not None and target is not source and _is_on_battlefield(game, target):
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))
