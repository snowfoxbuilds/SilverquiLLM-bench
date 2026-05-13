"""Card implementation for IntoTheRoil."""

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


class IntoTheRoil(Instant):
    """Into the Roil — {1}{U}

    Kicker {1}{U}.
    Return target nonland permanent to its owner's hand. If this spell
    was kicked, draw a card.

    FDN collector number 509.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Into the Roil")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {1}{U}\n"
            "Return target nonland permanent to its owner's hand. "
            "If this spell was kicked, draw a card.",
        )
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse("{1}{U}")

    def on_resolve(self, game: GameState) -> None:
        target = _get_target(self)
        if target is not None and _is_on_battlefield(game, target):
            from engine.zones import move_to_zone
            move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
        if self.kicked:
            from engine.game import draw_card
            controller = _get_controller(self)
            if controller is not None:
                draw_card(game, controller)


__all__ = ["IntoTheRoil"]
